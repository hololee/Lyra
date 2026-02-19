from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models import Setting
from .ssh_policy import connect_ssh, map_ssh_error


@dataclass
class HostSshSettings:
    host: str
    port: int
    username: str
    auth_method: str
    password: str | None
    host_fingerprint: str | None


@dataclass
class HostSshConfigError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _parse_ssh_port(value: int | str | None, default: int = 22) -> int:
    if isinstance(value, int):
        return value if value > 0 else default
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else default
    return default


def resolve_ssh_target_host(host: str) -> str:
    if host in {"localhost", "127.0.0.1"}:
        return "host.docker.internal"
    return host


def _normalize_auth_method(value: str | None) -> str:
    auth = (value or "password").strip().lower()
    if auth in {"password", "key"}:
        return auth
    return "password"


def _load_host_ssh_settings_from_payload(ssh_config: dict | None) -> HostSshSettings:
    raw = ssh_config or {}
    ssh_host = str(raw.get("host") or "").strip()
    ssh_port = _parse_ssh_port(raw.get("port"), 22)
    ssh_user = str(raw.get("username") or "").strip()
    ssh_auth_method = _normalize_auth_method(
        str(raw.get("authMethod") or raw.get("auth_method") or "").strip()
    )
    ssh_password = str(raw.get("password") or "").strip()
    ssh_host_fingerprint = str(raw.get("hostFingerprint") or raw.get("host_fingerprint") or "").strip()

    return HostSshSettings(
        host=ssh_host,
        port=ssh_port,
        username=ssh_user,
        auth_method=ssh_auth_method,
        password=ssh_password or None,
        host_fingerprint=ssh_host_fingerprint or None,
    )


async def _get_setting_value(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalars().first()
    return setting.value if setting else default


async def _load_host_ssh_settings_from_db(db: AsyncSession) -> HostSshSettings:
    ssh_host = await _get_setting_value(db, "ssh_host")
    ssh_port = _parse_ssh_port(await _get_setting_value(db, "ssh_port", "22"))
    ssh_user = await _get_setting_value(db, "ssh_username")
    ssh_auth_method = _normalize_auth_method(await _get_setting_value(db, "ssh_auth_method", "password"))
    ssh_password = await _get_setting_value(db, "ssh_password")
    ssh_host_fingerprint = await _get_setting_value(db, "ssh_host_fingerprint")
    return HostSshSettings(
        host=ssh_host.strip(),
        port=ssh_port,
        username=ssh_user.strip(),
        auth_method=ssh_auth_method,
        password=ssh_password.strip() or None,
        host_fingerprint=ssh_host_fingerprint.strip() or None,
    )


async def load_host_ssh_settings(
    db: AsyncSession | None,
    ssh_config: dict | None,
) -> HostSshSettings:
    payload = _load_host_ssh_settings_from_payload(ssh_config)

    if db is not None and hasattr(db, "execute"):
        legacy = await _load_host_ssh_settings_from_db(db)
        host = payload.host or legacy.host
        username = payload.username or legacy.username
        auth_method = payload.auth_method or legacy.auth_method
        password = payload.password if payload.password else legacy.password
        host_fingerprint = payload.host_fingerprint or legacy.host_fingerprint
        port = payload.port if payload.port > 0 else legacy.port
        payload = HostSshSettings(
            host=host,
            port=port,
            username=username,
            auth_method=auth_method,
            password=password,
            host_fingerprint=host_fingerprint,
        )

    if not payload.host or not payload.username or not payload.auth_method:
        raise HostSshConfigError(
            code="ssh_host_not_configured",
            message="Host server is not configured.",
        )
    if payload.auth_method == "password" and not payload.password:
        raise HostSshConfigError(
            code="ssh_host_not_configured",
            message="Host server is not configured.",
        )

    return payload


async def connect_host_ssh(
    db: AsyncSession | None = None,
    *,
    ssh_config: dict | None = None,
    private_key: str | None = None,
    timeout: int = 10,
):
    settings = await load_host_ssh_settings(db, ssh_config)
    return connect_ssh(
        host=resolve_ssh_target_host(settings.host),
        port=settings.port,
        username=settings.username,
        auth_method=settings.auth_method,
        password=settings.password,
        private_key=private_key,
        host_fingerprint=settings.host_fingerprint,
        timeout=timeout,
    )


def map_host_ssh_error(error: Exception) -> tuple[str, str]:
    if isinstance(error, HostSshConfigError):
        return error.code, error.message
    return map_ssh_error(error)
