"""Layer 1 — Business Ontology 빌더.

`data/terms.json`을 읽어 Neo4j에 다음을 멱등적으로 구축한다.
- :TermCategory 5개
- :Term 19개
- (:Term)-[:BELONGS_TO]->(:TermCategory)
- (:Term)-[:IS_A | RELATED_TO | SYNONYM_OF]->(:Term)

직접 실행: ``python -m backend.modeling.ontology.builders.layer1_business``
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..client import OntologyClient, close_client, get_client

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "terms.json"

# 허용된 Term-Term 관계 타입 (whitelist 기반 inject 방어)
ALLOWED_TERM_RELATIONS = {"IS_A", "RELATED_TO", "SYNONYM_OF"}


def load_seed() -> dict[str, Any]:
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def ensure_constraints(client: OntologyClient) -> None:
    """Term.id, TermCategory.id 의 unique 제약을 보장 (멱등)."""
    client.write(
        "CREATE CONSTRAINT term_id_unique IF NOT EXISTS "
        "FOR (t:Term) REQUIRE t.id IS UNIQUE"
    )
    client.write(
        "CREATE CONSTRAINT term_category_id_unique IF NOT EXISTS "
        "FOR (c:TermCategory) REQUIRE c.id IS UNIQUE"
    )


def clear_layer(client: OntologyClient) -> None:
    """Layer 1 노드만 삭제. Layer 2,3는 건드리지 않음."""
    client.write("MATCH (t:Term) DETACH DELETE t")
    client.write("MATCH (c:TermCategory) DETACH DELETE c")
    logger.info("Layer 1 cleared")


def upsert_categories(client: OntologyClient, categories: list[dict]) -> None:
    cypher = (
        "MERGE (c:TermCategory {id: $id}) "
        "SET c.korean_name = $korean_name, "
        "    c.description = $description"
    )
    statements = [(cypher, dict(cat)) for cat in categories]
    client.write_tx(statements)
    logger.info("Upserted %d TermCategory nodes", len(categories))


def upsert_terms(client: OntologyClient, terms: list[dict]) -> None:
    """Term 노드 upsert + BELONGS_TO 관계 생성."""
    now = datetime.now(timezone.utc).isoformat()
    cypher = (
        "MERGE (t:Term {id: $id}) "
        "SET t.korean_name = $korean_name, "
        "    t.english_name = $english_name, "
        "    t.aliases = $aliases, "
        "    t.category = $category, "
        "    t.description = $description, "
        "    t.created_at = coalesce(t.created_at, datetime($now)) "
        "WITH t "
        "MATCH (c:TermCategory {id: $category_id}) "
        "MERGE (t)-[:BELONGS_TO]->(c)"
    )
    statements: list[tuple[str, dict]] = []
    for term in terms:
        params = dict(term)
        params["category_id"] = f"cat_{term['category']}"
        params["now"] = now
        statements.append((cypher, params))
    client.write_tx(statements)
    logger.info("Upserted %d Term nodes (with BELONGS_TO)", len(terms))


def upsert_term_relations(client: OntologyClient, relations: list[dict]) -> None:
    """Term-Term 관계 upsert (IS_A / RELATED_TO / SYNONYM_OF)."""
    statements: list[tuple[str, dict]] = []
    for rel in relations:
        rel_type = rel["type"].upper()
        if rel_type not in ALLOWED_TERM_RELATIONS:
            raise ValueError(
                f"Disallowed Term relation type: {rel_type!r} "
                f"(allowed: {sorted(ALLOWED_TERM_RELATIONS)})"
            )
        # rel_type은 화이트리스트로 검증되었으므로 f-string 안전
        cypher = (
            "MATCH (a:Term {id: $from_id}) "
            "WITH a "
            "MATCH (b:Term {id: $to_id}) "
            f"MERGE (a)-[:{rel_type}]->(b)"
        )
        statements.append((cypher, {"from_id": rel["from"], "to_id": rel["to"]}))
    client.write_tx(statements)
    logger.info("Upserted %d Term-Term relations", len(relations))


def build(client: OntologyClient | None = None) -> dict[str, int]:
    """Layer 1 전체 빌드. 반환: 생성 카운트."""
    own_client = client is None
    client = client or get_client()
    try:
        seed = load_seed()
        ensure_constraints(client)
        clear_layer(client)
        upsert_categories(client, seed["categories"])
        upsert_terms(client, seed["terms"])
        upsert_term_relations(client, seed["relations"])

        counts = {
            "categories": len(seed["categories"]),
            "terms": len(seed["terms"]),
            "relations": len(seed["relations"]),
        }
        logger.info("Layer 1 build complete: %s", counts)
        return counts
    finally:
        if own_client:
            close_client()


def _verify(client: OntologyClient) -> None:
    """검증 쿼리 1, 2 실행."""
    print("\n=== 검증 쿼리 1: Term 개수 ===")
    rows = client.query("MATCH (t:Term) RETURN count(t) AS n")
    print(f"Term count = {rows[0]['n']} (expected 19)")
    assert rows[0]["n"] == 19, f"Expected 19 Terms, got {rows[0]['n']}"

    print("\n=== 검증 쿼리 2: 'Edging' 검색 ===")
    rows = client.query(
        "MATCH (t:Term) "
        "WHERE 'Edging' IN [t.korean_name, t.english_name] OR 'Edging' IN t.aliases "
        "RETURN t.id AS id"
    )
    ids = [r["id"] for r in rows]
    print(f"'Edging' → {ids} (expected ['term_edging'])")
    assert ids == ["term_edging"], f"Expected ['term_edging'], got {ids}"

    print("\n=== 추가 검증: Category, BELONGS_TO ===")
    rows = client.query("MATCH (c:TermCategory) RETURN count(c) AS n")
    print(f"TermCategory count = {rows[0]['n']} (expected 5)")
    assert rows[0]["n"] == 5

    rows = client.query("MATCH (:Term)-[r:BELONGS_TO]->(:TermCategory) RETURN count(r) AS n")
    print(f"BELONGS_TO count = {rows[0]['n']} (expected 19)")
    assert rows[0]["n"] == 19

    rows = client.query(
        "MATCH (:Term)-[r]->(:Term) "
        "WHERE type(r) IN ['IS_A','RELATED_TO','SYNONYM_OF'] "
        "RETURN count(r) AS n"
    )
    print(f"Term-Term relations = {rows[0]['n']} (expected 9)")
    assert rows[0]["n"] == 9

    print("\n✅ Layer 1 검증 통과")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    client = get_client()
    try:
        counts = build(client)
        print(f"\nBuild counts: {counts}")
        _verify(client)
    finally:
        close_client()


if __name__ == "__main__":
    main()
