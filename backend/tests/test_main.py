import sys
from unittest.mock import MagicMock

# Mock paramiko before importing app.main to avoid ImportError in environments without it
sys.modules["paramiko"] = MagicMock()

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_read_main():
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Lyra API"}
