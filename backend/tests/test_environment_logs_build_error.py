import asyncio
import uuid
from types import SimpleNamespace

import docker

from app.routers import environments as env_router


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def first(self):
        return self._items[0] if self._items else None


class _ExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarResult(self._items)


class _FakeDb:
    def __init__(self, env_row, settings):
        self._env = env_row
        self._settings = settings

    async def execute(self, stmt, *_args, **_kwargs):
        sql = str(stmt)
        params = stmt.compile().params

        if "FROM environments" in sql:
            wanted = str(params.get("id_1"))
            if str(self._env.id) == wanted:
                return _ExecuteResult([self._env])
            return _ExecuteResult([])

        if "FROM settings" in sql:
            wanted_key = str(params.get("key_1") or "")
            value = self._settings.get(wanted_key)
            if value is None:
                return _ExecuteResult([])
            return _ExecuteResult([SimpleNamespace(key=wanted_key, value=value)])

        return _ExecuteResult([])


def test_get_environment_logs_returns_build_failure_details_when_container_missing(monkeypatch):
    env_id = str(uuid.uuid4())
    env = SimpleNamespace(
        id=env_id,
        name="build-fail-env",
        status="error",
        worker_server_id=None,
    )
    build_error_key = f"build_error:{env_id}"
    db = _FakeDb(env, {build_error_key: "Build failed: syntax error at line 7"})

    class _ContainerStore:
        def get(self, _name):
            raise docker.errors.NotFound("missing")

    class _DockerClient:
        containers = _ContainerStore()

    monkeypatch.setattr(env_router.docker, "from_env", lambda: _DockerClient())

    result = asyncio.run(env_router.get_environment_logs(environment_id=env_id, db=db))

    logs = result.get("logs", "")
    assert "No container was created for this environment." in logs
    assert "[Build Failure Details]" in logs
    assert "Build failed: syntax error at line 7" in logs
