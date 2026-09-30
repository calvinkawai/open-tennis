from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from main import create_app


def test_private_api_requires_owner_and_preserves_confirmed_notes(tmp_path):
    settings = Settings(
        _env_file=None, sqlite_database_path=tmp_path / "app.db",
        tutorial_path=Path(__file__).parent / "fixtures",
        owner_password="local-test-password",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/wiki?space=technical").status_code == 401
        assert client.get("/docs").status_code == 401
        auth = ("owner", "local-test-password")
        assert client.get("/api/v1/status", auth=auth).json()["ready"]
        payload = {"client_id": str(uuid4()), "content": "I noticed more space."}
        first = client.post("/api/v1/journal", json=payload, auth=auth)
        assert first.status_code == 201
        replay = client.post("/api/v1/journal", json=payload, auth=auth)
        assert replay.json()["id"] == first.json()["id"]
        assert client.get("/api/v1/journal", auth=auth).json()[0]["content"] == payload["content"]
        invalid = client.post("/api/v1/journal", json={"content": "private-invalid-content"}, auth=auth)
        assert invalid.status_code == 422
        assert "private-invalid-content" not in invalid.text
        blocked = client.post("/api/v1/journal", json=payload, auth=auth, headers={
            "Origin": "https://untrusted.invalid",
        })
        assert blocked.status_code == 403


def test_missing_owner_configuration_fails_closed(tmp_path):
    settings = Settings(_env_file=None, sqlite_database_path=tmp_path / "unconfigured.db")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/journal").status_code == 503
        assert client.get("/health").status_code == 503
