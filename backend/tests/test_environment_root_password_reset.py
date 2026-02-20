import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import environments as env_router
from app.schemas import EnvironmentRootPasswordResetRequest


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def first(self):
        return self._item


class _ExecuteResult:
    def __init__(self, item):
        self._item = item

    def scalars(self):
        return _ScalarResult(self._item)


class _FakeDb:
    def __init__(self, env, *, fail_commit: bool = False):
        self._env = env
        self.commit_called = False
        self._fail_commit = fail_commit

    async def execute(self, _stmt, *_args, **_kwargs):
        return _ExecuteResult(self._env)

    async def commit(self):
        self.commit_called = True
        if self._fail_commit:
            raise RuntimeError("commit failed")


def _env(*, status="running", worker_server_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="test-env",
        status=status,
        worker_server_id=worker_server_id,
        root_password="__redacted__",
        root_password_encrypted="enc-old",
    )


def test_reset_root_password_host_success(monkeypatch):
    env = _env(status="running")
    db = _FakeDb(env)

    class _Container:
        status = "running"
        id = "container-123"

    class _Containers:
        def get(self, name):
            assert name == f"lyra-{env.name}-{env.id}"
            return _Container()

    class _Socket:
        def __init__(self):
            self.payload = b""

        def sendall(self, data: bytes):
            self.payload += data

        def close(self):
            return None

    sock = _Socket()

    class _DockerApi:
        def exec_create(self, container_id, cmd, stdin, tty):
            assert container_id == "container-123"
            assert cmd == ["chpasswd"]
            assert stdin is True
            assert tty is False
            return {"Id": "exec-1"}

        def exec_start(self, exec_id, detach, tty, socket):
            assert exec_id == "exec-1"
            assert detach is False
            assert tty is False
            assert socket is True
            return sock

        def exec_inspect(self, exec_id):
            assert exec_id == "exec-1"
            return {"ExitCode": 0}

    class _DockerClient:
        containers = _Containers()
        api = _DockerApi()

    monkeypatch.setattr(env_router.docker, "from_env", lambda: _DockerClient())
    monkeypatch.setattr(env_router, "encrypt_secret", lambda value: f"enc::{value}")

    result = asyncio.run(
        env_router.reset_environment_root_password(
            str(env.id),
            payload=EnvironmentRootPasswordResetRequest(new_password="newpass123"),
            db=db,
        )
    )

    assert result["message"] == "Root password updated"
    assert db.commit_called is True
    assert env.root_password == "__redacted__"
    assert env.root_password_encrypted == "enc::newpass123"
    assert sock.payload == b"root:newpass123\n"


def test_reset_root_password_rejects_worker_environment():
    env = _env(status="running", worker_server_id=uuid.uuid4())
    db = _FakeDb(env)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            env_router.reset_environment_root_password(
                str(env.id),
                payload=EnvironmentRootPasswordResetRequest(new_password="newpass123"),
                db=db,
            )
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "worker_reset_not_supported"
    assert db.commit_called is False


def test_reset_root_password_requires_running_environment(monkeypatch):
    env = _env(status="stopped")
    db = _FakeDb(env)
    monkeypatch.setattr(env_router, "_is_host_environment_running_now", lambda _env: False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            env_router.reset_environment_root_password(
                str(env.id),
                payload=EnvironmentRootPasswordResetRequest(new_password="newpass123"),
                db=db,
            )
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "environment_not_running"
    assert db.commit_called is False


def test_reset_root_password_rejects_weak_password():
    env = _env(status="running")
    db = _FakeDb(env)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            env_router.reset_environment_root_password(
                str(env.id),
                payload=EnvironmentRootPasswordResetRequest(new_password="a"),
                db=db,
            )
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "weak_password"


def test_reset_root_password_container_not_found(monkeypatch):
    env = _env(status="running")
    db = _FakeDb(env)

    class _Containers:
        def get(self, _name):
            raise env_router.docker.errors.NotFound("missing")

    class _DockerClient:
        containers = _Containers()

    monkeypatch.setattr(env_router.docker, "from_env", lambda: _DockerClient())
    monkeypatch.setattr(env_router, "encrypt_secret", lambda value: f"enc::{value}")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            env_router.reset_environment_root_password(
                str(env.id),
                payload=EnvironmentRootPasswordResetRequest(new_password="newpass123"),
                db=db,
            )
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "container_not_found"


def test_reset_root_password_exec_failure_hides_sensitive_output(monkeypatch):
    env = _env(status="running")
    db = _FakeDb(env)

    class _Container:
        status = "running"
        id = "container-123"

    class _Containers:
        def get(self, _name):
            return _Container()

    class _Socket:
        def sendall(self, _data: bytes):
            return None

        def close(self):
            return None

    class _DockerApi:
        def exec_create(self, *_args, **_kwargs):
            return {"Id": "exec-1"}

        def exec_start(self, *_args, **_kwargs):
            return _Socket()

        def exec_inspect(self, _exec_id):
            return {"ExitCode": 1}

    class _DockerClient:
        containers = _Containers()
        api = _DockerApi()

    monkeypatch.setattr(env_router.docker, "from_env", lambda: _DockerClient())
    monkeypatch.setattr(env_router, "encrypt_secret", lambda value: f"enc::{value}")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            env_router.reset_environment_root_password(
                str(env.id),
                payload=EnvironmentRootPasswordResetRequest(new_password="newpass123"),
                db=db,
            )
        )

    assert exc.value.status_code == 500
    assert exc.value.detail["code"] == "root_password_reset_failed"
    assert "newpass123" not in str(exc.value.detail)


def test_reset_root_password_commit_failure_reports_sync_error(monkeypatch):
    env = _env(status="running")
    db = _FakeDb(env, fail_commit=True)

    class _Container:
        status = "running"
        id = "container-123"

    class _Containers:
        def get(self, _name):
            return _Container()

    class _Socket:
        def sendall(self, _data: bytes):
            return None

        def close(self):
            return None

    class _DockerApi:
        def __init__(self):
            self._exec_count = 0

        def exec_create(self, *_args, **_kwargs):
            self._exec_count += 1
            return {"Id": f"exec-{self._exec_count}"}

        def exec_start(self, *_args, **_kwargs):
            return _Socket()

        def exec_inspect(self, _exec_id):
            return {"ExitCode": 0}

    class _DockerClient:
        containers = _Containers()
        api = _DockerApi()

    monkeypatch.setattr(env_router.docker, "from_env", lambda: _DockerClient())
    monkeypatch.setattr(env_router, "encrypt_secret", lambda value: f"enc::{value}")
    monkeypatch.setattr(env_router, "decrypt_secret", lambda _v: "oldpass")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            env_router.reset_environment_root_password(
                str(env.id),
                payload=EnvironmentRootPasswordResetRequest(new_password="newpass123"),
                db=db,
            )
        )

    assert exc.value.status_code == 500
    assert exc.value.detail["code"] == "password_metadata_sync_failed"
