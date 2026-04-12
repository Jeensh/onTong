from unittest.mock import MagicMock, patch

from backend.modeling.infrastructure.neo4j_client import Neo4jClient


@patch("backend.modeling.infrastructure.neo4j_client.GraphDatabase.driver")
class TestNeo4jClient:
    def test_connect_and_verify(self, mock_gdb_driver):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        assert client.uri == "bolt://localhost:7687"
        mock_gdb_driver.assert_called_once_with("bolt://localhost:7687", auth=("neo4j", "ontong_dev"))

    def test_health_check_returns_dict(self, mock_gdb_driver):
        mock_driver = MagicMock()
        mock_gdb_driver.return_value = mock_driver
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        mock_driver.verify_connectivity.return_value = None
        result = client.health()
        assert result["status"] == "healthy"

    def test_run_query(self, mock_gdb_driver):
        mock_driver = MagicMock()
        mock_gdb_driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute_read.return_value = [{"n": 1}]
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        result = client.query("RETURN 1 as n")
        assert result == [{"n": 1}]

    def test_close(self, mock_gdb_driver):
        mock_driver = MagicMock()
        mock_gdb_driver.return_value = mock_driver
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        client.close()
        mock_driver.close.assert_called_once()
