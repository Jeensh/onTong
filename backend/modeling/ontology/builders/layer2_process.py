"""Layer 2 — Process Ontology 빌더.

`data/steps.json`, `standards.json`, `variables.json`, `error_codes.json`을
읽어 Neo4j에 다음을 멱등적으로 구축한다.

노드:
- :Step (12)
- :Standard (14)
- :Variable (10)
- :ErrorCode (1)

관계:
- (:Step)-[:PRECEDES]->(:Step)
- (:Step)-[:DEPENDS_ON {via_variable}]->(:Step)
- (:Step)-[:USES_STANDARD]->(:Standard)
- (:Step)-[:REQUIRES_INPUT]->(:Variable)
- (:Step)-[:PRODUCES_OUTPUT]->(:Variable)
- (:Standard)-[:CONSTRAINS]->(:Variable)
- (:Step)-[:TRIGGERS_ON_FAIL]->(:ErrorCode)

직접 실행: ``python -m backend.modeling.ontology.builders.layer2_process``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..client import OntologyClient, close_client, get_client

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def ensure_constraints(client: OntologyClient) -> None:
    """Layer 2 노드의 unique 제약 보장 (멱등)."""
    statements = [
        "CREATE CONSTRAINT step_id_unique IF NOT EXISTS "
        "FOR (s:Step) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT step_number_unique IF NOT EXISTS "
        "FOR (s:Step) REQUIRE s.step_number IS UNIQUE",
        "CREATE CONSTRAINT standard_id_unique IF NOT EXISTS "
        "FOR (s:Standard) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT standard_code_unique IF NOT EXISTS "
        "FOR (s:Standard) REQUIRE s.code IS UNIQUE",
        "CREATE CONSTRAINT variable_id_unique IF NOT EXISTS "
        "FOR (v:Variable) REQUIRE v.id IS UNIQUE",
        "CREATE CONSTRAINT errorcode_code_unique IF NOT EXISTS "
        "FOR (e:ErrorCode) REQUIRE e.code IS UNIQUE",
    ]
    for cypher in statements:
        client.write(cypher)


def clear_layer(client: OntologyClient) -> None:
    """Layer 2 노드만 삭제. Layer 1, 3는 건드리지 않음."""
    for label in ("Step", "Standard", "Variable", "ErrorCode"):
        client.write(f"MATCH (n:{label}) DETACH DELETE n")
    logger.info("Layer 2 cleared")


def upsert_steps(client: OntologyClient, steps: list[dict]) -> None:
    cypher = (
        "MERGE (s:Step {id: $id}) "
        "SET s.step_number = $step_number, "
        "    s.korean_name = $korean_name, "
        "    s.english_name = $english_name, "
        "    s.description = $description, "
        "    s.formula = $formula, "
        "    s.task_id = $task_id, "
        "    s.step_type = $step_type"
    )
    statements: list[tuple[str, dict]] = []
    for step in steps:
        params = {
            "id": step["id"],
            "step_number": step["step_number"],
            "korean_name": step["korean_name"],
            "english_name": step["english_name"],
            "description": step["description"],
            "formula": step.get("formula"),
            "task_id": step["task_id"],
            "step_type": step["step_type"],
        }
        statements.append((cypher, params))
    client.write_tx(statements)
    logger.info("Upserted %d Step nodes", len(steps))


def upsert_step_relations(
    client: OntologyClient,
    precedence: list[list[int]],
    depends_on: list[dict],
) -> None:
    """Step 간 PRECEDES, DEPENDS_ON 관계."""
    statements: list[tuple[str, dict]] = []
    for a, b in precedence:
        statements.append(
            (
                "MATCH (s1:Step {step_number: $a}) "
                "WITH s1 "
                "MATCH (s2:Step {step_number: $b}) "
                "MERGE (s1)-[:PRECEDES]->(s2)",
                {"a": a, "b": b},
            )
        )
    for dep in depends_on:
        statements.append(
            (
                "MATCH (s1:Step {step_number: $from_n}) "
                "WITH s1 "
                "MATCH (s2:Step {step_number: $to_n}) "
                "MERGE (s1)-[r:DEPENDS_ON]->(s2) "
                "SET r.via_variable = $via_variable",
                {
                    "from_n": dep["from"],
                    "to_n": dep["to"],
                    "via_variable": dep["via_variable"],
                },
            )
        )
    client.write_tx(statements)
    logger.info(
        "Upserted Step relations: %d PRECEDES + %d DEPENDS_ON",
        len(precedence),
        len(depends_on),
    )


def upsert_standards(client: OntologyClient, standards: list[dict]) -> None:
    cypher = (
        "MERGE (s:Standard {id: $id}) "
        "SET s.code = $code, "
        "    s.korean_name = $korean_name, "
        "    s.english_name = $english_name, "
        "    s.category = $category, "
        "    s.description = $description"
    )
    statements = [(cypher, dict(std)) for std in standards]
    client.write_tx(statements)
    logger.info("Upserted %d Standard nodes", len(standards))


def upsert_step_uses_standard(
    client: OntologyClient, mapping: dict[str, list[str]]
) -> int:
    """Step USES_STANDARD Standard."""
    statements: list[tuple[str, dict]] = []
    count = 0
    for step_num_str, codes in mapping.items():
        step_num = int(step_num_str)
        for code in codes:
            statements.append(
                (
                    "MATCH (s:Step {step_number: $step_num}) "
                    "WITH s "
                    "MATCH (std:Standard {code: $code}) "
                    "MERGE (s)-[:USES_STANDARD]->(std)",
                    {"step_num": step_num, "code": code},
                )
            )
            count += 1
    client.write_tx(statements)
    logger.info("Upserted %d USES_STANDARD relations", count)
    return count


def upsert_variables(client: OntologyClient, variables: list[dict]) -> None:
    cypher = (
        "MERGE (v:Variable {id: $id}) "
        "SET v.name = $name, "
        "    v.korean_name = $korean_name, "
        "    v.type = $type, "
        "    v.unit = $unit, "
        "    v.valid_range = $valid_range"
    )
    statements: list[tuple[str, dict]] = []
    for var in variables:
        params = {
            "id": var["id"],
            "name": var["name"],
            "korean_name": var["korean_name"],
            "type": var["type"],
            "unit": var.get("unit"),
            "valid_range": var.get("valid_range"),
        }
        statements.append((cypher, params))
    client.write_tx(statements)
    logger.info("Upserted %d Variable nodes", len(variables))


def upsert_step_variables(
    client: OntologyClient,
    inputs: dict[str, list[str]],
    outputs: dict[str, list[str]],
) -> tuple[int, int]:
    """Step REQUIRES_INPUT / PRODUCES_OUTPUT Variable."""
    statements: list[tuple[str, dict]] = []
    in_count = 0
    out_count = 0
    for step_num_str, var_ids in inputs.items():
        step_num = int(step_num_str)
        for var_id in var_ids:
            statements.append(
                (
                    "MATCH (s:Step {step_number: $step_num}) "
                    "WITH s "
                    "MATCH (v:Variable {id: $var_id}) "
                    "MERGE (s)-[:REQUIRES_INPUT]->(v)",
                    {"step_num": step_num, "var_id": var_id},
                )
            )
            in_count += 1
    for step_num_str, var_ids in outputs.items():
        step_num = int(step_num_str)
        for var_id in var_ids:
            statements.append(
                (
                    "MATCH (s:Step {step_number: $step_num}) "
                    "WITH s "
                    "MATCH (v:Variable {id: $var_id}) "
                    "MERGE (s)-[:PRODUCES_OUTPUT]->(v)",
                    {"step_num": step_num, "var_id": var_id},
                )
            )
            out_count += 1
    client.write_tx(statements)
    logger.info(
        "Upserted %d REQUIRES_INPUT + %d PRODUCES_OUTPUT relations",
        in_count,
        out_count,
    )
    return in_count, out_count


def upsert_standard_constrains(
    client: OntologyClient, items: list[dict]
) -> None:
    """Standard CONSTRAINS Variable."""
    statements: list[tuple[str, dict]] = []
    for item in items:
        statements.append(
            (
                "MATCH (std:Standard {code: $code}) "
                "WITH std "
                "MATCH (v:Variable {id: $var_id}) "
                "MERGE (std)-[:CONSTRAINS]->(v)",
                {"code": item["standard"], "var_id": item["variable"]},
            )
        )
    client.write_tx(statements)
    logger.info("Upserted %d CONSTRAINS relations", len(items))


def upsert_error_codes(
    client: OntologyClient,
    error_codes: list[dict],
    triggers: list[dict],
) -> None:
    """ErrorCode 노드 + Step TRIGGERS_ON_FAIL ErrorCode."""
    code_cypher = (
        "MERGE (e:ErrorCode {code: $code}) "
        "SET e.korean_message = $korean_message, "
        "    e.cause = $cause, "
        "    e.severity = $severity, "
        "    e.trigger_condition = $trigger_condition"
    )
    statements: list[tuple[str, dict]] = []
    for ec in error_codes:
        params = {
            "code": ec["code"],
            "korean_message": ec["korean_message"],
            "cause": ec["cause"],
            "severity": ec.get("severity", "error"),
            "trigger_condition": ec["trigger_condition"],
        }
        statements.append((code_cypher, params))
    for trig in triggers:
        statements.append(
            (
                "MATCH (s:Step {step_number: $step_num}) "
                "WITH s "
                "MATCH (e:ErrorCode {code: $code}) "
                "MERGE (s)-[:TRIGGERS_ON_FAIL]->(e)",
                {"step_num": trig["step_number"], "code": trig["error_code"]},
            )
        )
    client.write_tx(statements)
    logger.info(
        "Upserted %d ErrorCode + %d TRIGGERS_ON_FAIL relations",
        len(error_codes),
        len(triggers),
    )


def build(client: OntologyClient | None = None) -> dict[str, int]:
    own_client = client is None
    client = client or get_client()
    try:
        steps_data = _load("steps.json")
        std_data = _load("standards.json")
        var_data = _load("variables.json")
        err_data = _load("error_codes.json")

        ensure_constraints(client)
        clear_layer(client)

        upsert_steps(client, steps_data["steps"])
        upsert_step_relations(
            client, steps_data["precedence"], steps_data["depends_on"]
        )
        upsert_standards(client, std_data["standards"])
        uses_count = upsert_step_uses_standard(client, std_data["step_uses_standard"])
        upsert_variables(client, var_data["variables"])
        in_count, out_count = upsert_step_variables(
            client, var_data["step_inputs"], var_data["step_outputs"]
        )
        upsert_standard_constrains(client, var_data["standard_constrains"])
        upsert_error_codes(
            client, err_data["error_codes"], err_data["step_triggers_error"]
        )

        counts = {
            "steps": len(steps_data["steps"]),
            "standards": len(std_data["standards"]),
            "variables": len(var_data["variables"]),
            "error_codes": len(err_data["error_codes"]),
            "precedes": len(steps_data["precedence"]),
            "depends_on": len(steps_data["depends_on"]),
            "uses_standard": uses_count,
            "requires_input": in_count,
            "produces_output": out_count,
            "constrains": len(var_data["standard_constrains"]),
            "triggers_on_fail": len(err_data["step_triggers_error"]),
        }
        logger.info("Layer 2 build complete: %s", counts)
        return counts
    finally:
        if own_client:
            close_client()


def _verify(client: OntologyClient) -> None:
    """검증 쿼리 3 + 추가 무결성 체크."""
    print("\n=== 검증 쿼리 3: SC070을 사용하는 Step ===")
    rows = client.query(
        "MATCH (s:Step)-[:USES_STANDARD]->(:Standard {code: 'SC070'}) "
        "RETURN s.step_number AS n, s.korean_name AS name "
        "ORDER BY s.step_number"
    )
    pretty = [(r["n"], r["name"]) for r in rows]
    print(f"SC070 사용 Step → {pretty}")
    assert [n for n, _ in pretty] == [2, 13], (
        f"Expected [2, 13], got {[n for n, _ in pretty]}"
    )

    print("\n=== 추가 검증: 노드 카운트 ===")
    expectations = [
        ("Step", 12),
        ("Standard", 14),
        ("Variable", 10),
        ("ErrorCode", 1),
    ]
    for label, expected in expectations:
        rows = client.query(f"MATCH (n:{label}) RETURN count(n) AS n")
        actual = rows[0]["n"]
        print(f"{label} = {actual} (expected {expected})")
        assert actual == expected, f"{label}: {actual} != {expected}"

    print("\n=== 추가 검증: 관계 카운트 ===")
    # NOTE: 시드 §H의 ~14, ~7은 근사 표기. 실제 시드 카운트로 검증.
    rel_expectations = [
        ("PRECEDES", 11),
        ("DEPENDS_ON", 2),
        ("USES_STANDARD", 22),
        ("REQUIRES_INPUT", 12),
        ("PRODUCES_OUTPUT", 7),
        ("CONSTRAINS", 5),
        ("TRIGGERS_ON_FAIL", 1),
    ]
    for rel, expected in rel_expectations:
        rows = client.query(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n")
        actual = rows[0]["n"]
        print(f"{rel} = {actual} (expected {expected})")
        assert actual == expected, f"{rel}: {actual} != {expected}"

    print("\n✅ Layer 2 검증 통과")


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
