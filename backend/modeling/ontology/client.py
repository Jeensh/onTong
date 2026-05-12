"""Section 2 Modeling — 3-Layer Ontology Neo4j 클라이언트.

스펙(`docs/simulation/ontology-modeling-spec.md` Section 2)에 따른 신규 클라이언트.
기존 `backend/modeling/infrastructure/neo4j_client.py`와 별도로,
3-Layer 온톨로지(Term/Step/Standard/Class/Method 등) 전용 진입점이다.

사용 예시:
    from backend.modeling.ontology.client import get_client
    client = get_client()
    result = client.query("MATCH (t:Term) RETURN count(t) AS n")

직접 실행:
    python -m backend.modeling.ontology.client
"""

from __future__ import annotations

import logging
import os
from typing import Any

from neo4j import Driver, GraphDatabase

logger = logging.getLogger(__name__)


class OntologyClient:
    """3-Layer 온톨로지 전용 Neo4j 클라이언트.

    스펙의 호출 패턴(``client.query(cypher, **kwargs)``)을 지원한다.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri = uri
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("OntologyClient created for %s", uri)

    def verify(self) -> dict[str, str]:
        try:
            self._driver.verify_connectivity()
            return {"status": "healthy", "uri": self.uri}
        except Exception as exc:  # noqa: BLE001 — surface any driver error to caller
            return {"status": "unhealthy", "error": str(exc)}

    def query(self, cypher: str, **params: Any) -> list[dict]:
        with self._driver.session() as session:
            return session.execute_read(lambda tx: tx.run(cypher, **params).data())

    def write(self, cypher: str, **params: Any) -> None:
        with self._driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher, **params))

    def write_tx(self, statements: list[tuple[str, dict[str, Any]]]) -> None:
        """다수 쓰기를 단일 트랜잭션으로 실행. 빌더 멱등성 보장에 사용."""

        def _work(tx):
            for cypher, p in statements:
                tx.run(cypher, **p)

        with self._driver.session() as session:
            session.execute_write(_work)

    def close(self) -> None:
        self._driver.close()
        logger.info("OntologyClient closed")


_client: OntologyClient | None = None


def get_client() -> OntologyClient:
    """프로세스 단일 인스턴스 반환. 환경변수 NEO4J_URI/USER/PASSWORD 사용."""
    global _client
    if _client is None:
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "ontong_password_2026")
        _client = OntologyClient(uri, user, password)
    return _client


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _hello() -> None:
    """연결 확인용 간이 진입점.

    실행: ``python -m backend.modeling.ontology.client``
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # .env 파일이 있으면 자동 로드 (python-dotenv는 선택적 의존성)
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    client = get_client()
    health = client.verify()
    print(f"[health] {health}")
    if health["status"] != "healthy":
        raise SystemExit(1)

    rows = client.query("RETURN 'Hello onTong!' AS greeting")
    print(rows[0]["greeting"])
    close_client()


if __name__ == "__main__":
    _hello()
