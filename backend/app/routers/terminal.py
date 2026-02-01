from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import asyncio
import logging
import paramiko
from ..database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..models import Setting
import io
import json
from pydantic import BaseModel
from typing import Optional


router = APIRouter(
    prefix="/terminal",
    tags=["terminal"],
)


logger = logging.getLogger("uvicorn")


class SshTestRequest(BaseModel):
    host: str
    port: int
    username: str
    authMethod: str
    password: Optional[str] = None
    privateKey: Optional[str] = None


@router.post("/test-ssh")
async def test_ssh_connection(req: SshTestRequest):
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        target_host = req.host
        if target_host in ["localhost", "127.0.0.1"]:
            target_host = "host.docker.internal"

        if req.authMethod == "key" and req.privateKey:
            key_file = io.StringIO(req.privateKey)
            try:
                pkey = paramiko.RSAKey.from_private_key(key_file)
            except Exception:
                try:
                    key_file.seek(0)
                    pkey = paramiko.Ed25519Key.from_private_key(key_file)
                except Exception:
                    key_file.seek(0)
                    pkey = paramiko.PKey.from_private_key(key_file)
            ssh_client.connect(target_host, port=req.port, username=req.username, pkey=pkey, timeout=5)
        else:
            ssh_client.connect(target_host, port=req.port, username=req.username, password=req.password, timeout=5)

        ssh_client.close()
        return {"status": "success", "message": "Successfully connected to host."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_setting_value(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalars().first()
    return setting.value if setting else default


@router.websocket("/ws")
async def websocket_terminal(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()

    ssh_host = await get_setting_value(db, "ssh_host")
    ssh_port_str = await get_setting_value(db, "ssh_port", "22")
    ssh_port = int(ssh_port_str) if ssh_port_str.isdigit() else 22
    ssh_user = await get_setting_value(db, "ssh_username")
    ssh_auth_method = await get_setting_value(db, "ssh_auth_method", "password")
    ssh_password = await get_setting_value(db, "ssh_password")

    ssh_client = None
    chan = None

    try:
        # Wait for INIT message from client
        init_raw = await websocket.receive_text()
        init_data = json.loads(init_raw)

        if init_data.get("type") != "INIT":
            await websocket.close()
            return

        ssh_key = init_data.get("privateKey")
        cols = init_data.get("cols", 80)
        rows = init_data.get("rows", 24)

        if ssh_host and ssh_user:
            target_host = ssh_host
            if target_host in ["localhost", "127.0.0.1"]:
                target_host = "host.docker.internal"

            try:
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                if ssh_auth_method == "key" and ssh_key:
                    key_file = io.StringIO(ssh_key)
                    try:
                        pkey = paramiko.RSAKey.from_private_key(key_file)
                    except Exception:
                        try:
                            key_file.seek(0)
                            pkey = paramiko.Ed25519Key.from_private_key(key_file)
                        except Exception:
                            key_file.seek(0)
                            pkey = paramiko.PKey.from_private_key(key_file)
                    ssh_client.connect(target_host, port=ssh_port, username=ssh_user, pkey=pkey, timeout=10)
                else:
                    ssh_client.connect(target_host, port=ssh_port, username=ssh_user, password=ssh_password, timeout=10)

                chan = ssh_client.invoke_shell(term='xterm-256color', width=cols, height=rows)
                chan.setblocking(0)
                await websocket.send_text(f"\x1b[32mConnected to host {ssh_host} via SSH\x1b[0m\r\n")
            except Exception as e:
                logger.error(f"SSH connection failed: {e}")
                await websocket.send_text(f"\x1b[31mSSH Connection Failed: {e}\x1b[0m\r\n")
                await websocket.close()
                return
        else:
            await websocket.send_text("\x1b[31mError: Host server not configured. Please check terminal settings.\x1b[0m\r\n")
            await websocket.close()
            return

        async def write_to_backend():
            while True:
                try:
                    data = await websocket.receive_text()
                    if data.startswith("RESIZE:"):
                        _, dims = data.split(":")
                        r, c = map(int, dims.split(","))
                        if chan:
                            chan.resize_pty(width=c, height=r)
                    else:
                        if chan:
                            chan.send(data)
                except (WebSocketDisconnect, Exception):
                    break

        async def read_from_backend():
            while True:
                try:
                    if chan:
                        if chan.recv_ready():
                            data = chan.recv(10240)
                            if not data:
                                break
                            await websocket.send_bytes(data)
                        else:
                            await asyncio.sleep(0.01)

                    if chan and chan.exit_status_ready():
                        break
                except Exception:
                    break

        writer_task = asyncio.create_task(write_to_backend())
        reader_task = asyncio.create_task(read_from_backend())

        await asyncio.wait(
            [writer_task, reader_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        writer_task.cancel()
        reader_task.cancel()

    except Exception as e:
        logger.error(f"Terminal error: {e}")
    finally:
        if chan:
            chan.close()
        if ssh_client:
            ssh_client.close()
        try:
            await websocket.close()
        except Exception:
            pass
