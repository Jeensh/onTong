import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestModelingHealthAPI:
    def test_health_endpoint(self):
        from backend.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/modeling/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["section"] == "modeling"
        assert "code_analysis" in data["capabilities"]
