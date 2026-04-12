"""Neo4j connection client for Section 2 graph storage."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thin wrapper around Neo4j driver with health check and query helpers."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri = uri
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Neo4j client created for {uri}")

    def health(self) -> dict[str, str]:
        try:
            self._driver.verify_connectivity()
            return {"status": "healthy", "uri": self.uri}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        with self._driver.session() as session:
            return session.execute_read(lambda tx: tx.run(cypher, params or {}).data())

    def write(self, cypher: str, params: dict[str, Any] | None = None) -> None:
        with self._driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher, params or {}))

    def write_tx(self, cypher_list: list[tuple[str, dict]]) -> None:
        """Execute multiple writes in a single transaction."""
        def _work(tx):
            for cypher, params in cypher_list:
                tx.run(cypher, params)
        with self._driver.session() as session:
            session.execute_write(_work)

    def close(self) -> None:
        self._driver.close()
        logger.info("Neo4j client closed")
