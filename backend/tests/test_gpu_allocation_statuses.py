import asyncio
from uuid import uuid4

from app.routers.environments import _collect_used_gpu_indices


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _ExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarResult(self._items)


class _FakeEnv:
    def __init__(self, status: str, gpu_indices):
        self.status = status
        self.gpu_indices = gpu_indices


class _FakeDb:
    def __init__(self, envs):
        self._envs = envs
        self.last_stmt = None

    async def execute(self, *args, **_kwargs):
        if args:
            self.last_stmt = args[0]
        return _ExecuteResult(self._envs)


def test_collect_used_gpu_indices_includes_creating_and_excludes_stopped():
    db = _FakeDb(
        [
            _FakeEnv("creating", [0]),
            _FakeEnv("building", [1]),
            _FakeEnv("running", [2]),
            _FakeEnv("starting", [3]),
            _FakeEnv("stopped", [4]),
            _FakeEnv("error", [5]),
        ]
    )

    used = asyncio.run(_collect_used_gpu_indices(db))

    assert used == {0, 1, 2, 3}


def test_collect_used_gpu_indices_scopes_to_host_when_worker_not_provided():
    db = _FakeDb([_FakeEnv("running", [0])])

    asyncio.run(_collect_used_gpu_indices(db, None))

    assert db.last_stmt is not None
    assert "worker_server_id IS NULL" in str(db.last_stmt)


def test_collect_used_gpu_indices_scopes_to_selected_worker():
    db = _FakeDb([_FakeEnv("running", [0])])
    worker_id = uuid4()

    asyncio.run(_collect_used_gpu_indices(db, worker_id))

    assert db.last_stmt is not None
    assert "worker_server_id" in str(db.last_stmt)
