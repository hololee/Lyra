import importlib
import sys
from unittest.mock import MagicMock


def _load_main_app():
    sys.modules["paramiko"] = MagicMock()
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    import app.main as main_module  # noqa: WPS433

    return importlib.reload(main_module).app


def _route_paths(app):
    return {route.path for route in app.routes}


def test_worker_role_exposes_only_worker_api(monkeypatch):
    monkeypatch.setenv("LYRA_NODE_ROLE", "worker")
    app = _load_main_app()
    paths = _route_paths(app)

    assert "/api/worker/health" in paths
    assert "/api/environments/" not in paths
    assert "/api/settings/{key}" not in paths
    assert "/api/worker-servers/" not in paths


def test_main_role_exposes_main_and_worker_routes(monkeypatch):
    monkeypatch.setenv("LYRA_NODE_ROLE", "main")
    app = _load_main_app()
    paths = _route_paths(app)

    assert "/api/worker/health" in paths
    assert "/api/environments/" in paths
    assert "/api/settings/{key}" in paths
    assert "/api/worker-servers/" in paths
