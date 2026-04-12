import pytest
from unittest.mock import MagicMock, patch

from backend.modeling.infrastructure.neo4j_client import Neo4jClient


class TestNeo4jClient:
    def test_connect_and_verify(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        assert client.uri == "bolt://localhost:7687"

    def test_health_check_returns_dict(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        with patch.object(client, '_driver') as mock_driver:
            mock_driver.verify_connectivity.return_value = None
            result = client.health()
            assert result["status"] == "healthy"

    def test_run_query(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        with patch.object(client, '_driver') as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value.data.return_value = [{"n": 1}]
            result = client.query("RETURN 1 as n")
            assert result == [{"n": 1}]

    def test_close(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        with patch.object(client, '_driver') as mock_driver:
            client.close()
            mock_driver.close.assert_called_once()
