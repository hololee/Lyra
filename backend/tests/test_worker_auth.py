from app.core import worker_auth


def test_ensure_worker_api_token_persists_and_reloads(tmp_path, monkeypatch):
    token_file = tmp_path / "worker" / "token.txt"
    monkeypatch.setenv("LYRA_NODE_ROLE", worker_auth.WORKER_ROLE)
    monkeypatch.setenv("LYRA_WORKER_RUNTIME_TOKEN_FILE", str(token_file))
    monkeypatch.setattr(worker_auth, "_WORKER_RUNTIME_TOKEN", None)

    first = worker_auth.ensure_worker_api_token()
    assert first
    assert token_file.exists()
    assert token_file.read_text(encoding="utf-8").strip() == first

    # Simulate process restart by clearing runtime cache; token should be reloaded from file.
    monkeypatch.setattr(worker_auth, "_WORKER_RUNTIME_TOKEN", None)
    second = worker_auth.ensure_worker_api_token()
    assert second == first


def test_ensure_worker_api_token_returns_empty_for_main_role(monkeypatch):
    monkeypatch.setenv("LYRA_NODE_ROLE", worker_auth.MAIN_ROLE)
    monkeypatch.setattr(worker_auth, "_WORKER_RUNTIME_TOKEN", None)
    assert worker_auth.ensure_worker_api_token() == ""
