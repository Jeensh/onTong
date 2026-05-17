"""Bridge 빌더 — Layer 1 ↔ Layer 2, Layer 2 ↔ Layer 3.

`data/bridges.json`을 읽어 다음 관계를 멱등적으로 구축한다.
- Layer 1 ↔ 2: (:Term)-[:REFERS_TO_PROCESS {role}]->(:Step)
- Layer 2 ↔ 3:
    - (:Method)-[:CALCULATES]->(:Step)         — Stage 1 정규식 + Stage 2 LLM(옵션)
    - (:Class)-[:IMPLEMENTS]->(:Step)          — Service 클래스가 Step을 구현
    - (:Class)-[:RELATES_TO_STANDARD]->(:Standard)  — Form 클래스가 SC 기준에 매핑

직접 실행: ``python -m backend.modeling.ontology.builders.bridges``
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..client import OntologyClient, close_client, get_client

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "bridges.json"

ALLOWED_ROLES = {"input", "output", "internal", "error_trigger"}

# 스펙 §6-2 Stage 1 — Naming Convention 패턴.
# specificity 높은 순서로 평가하여 Step 12/13 등이 충돌하지 않도록 한다.
METHOD_TO_STEP_PATTERNS: list[tuple[str, int]] = [
    (r"^calculate.*Target.*Width.*[Ff]or.*3[Pp]ass.*", 13),
    (r"^calculate.*SecondaryWeight.*Lower.*", 5),
    (r"^calculate.*SecondaryWeight.*Upper.*", 6),
    (r"^calculate.*Thickness.*", 1),
    (r"^calculate.*PrimaryWidth.*", 2),
    (r"^calculate.*PrimaryLength.*", 3),
    (r"^calculate.*PrimaryWeight.*", 4),
    (r"^calculate.*UnitCount.*", 8),  # calculateUnitCountAndTargetWeight (Step 8)
    (r"^calculate.*MaxSplitCount.*", 7),
    (r"^calculate.*Split.*Count.*", 7),
    (r"^check.*TargetWeight.*", 9),  # checkTargetWeightSatisfaction (Step 9)
    (r"^calculate.*SecondaryWidth.*", 10),
    (r"^calculate.*SecondaryLength.*", 11),  # calculateSecondaryLengthRange (Step 11)
    (r"^calculate.*Target.*Length.*", 14),
    (r"^calculate.*Target.*Width.*", 12),
]

# 스펙 §E-2 — Form 클래스 ↔ SC 기준 매핑.
FORM_TO_STANDARD: dict[str, str] = {
    "SDCastMachineSpecForm": "SC030",
    "SDHsmMachineSpecForm": "SC040",
    "SDCoilOutDiaRestricForm": "SC060",
    "SDHsmEdgingSpecForm": "SC070",
    "SDHrEdgingSpecGroupForm": "SC071",
    "SDHsmWeightMinForm": "SC080",
    "SDStdRollMaxUnitForm": "SC090",
    "SDCsmMinWgtForm": "SC100",
    "SDOemWgtMaxRangeForm": "SC110",
    "SDWgtSatisfactionConstForm": "SC160",
    "SDHotCoilNotCuttableSpecForm": "SC170",
    "SDSlabDesignLimitationForm": "SC270",
    "SDSpecificCustomerWgtRestriForm": "SC290",
    "SDDeliveryAllowanceForm": "SC370",
}


def load_seed() -> dict[str, Any]:
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def clear_layer1_to_layer2(client: OntologyClient) -> None:
    """Layer 1↔2 Bridge 관계만 삭제. 노드는 보존."""
    client.write("MATCH (:Term)-[r:REFERS_TO_PROCESS]->(:Step) DELETE r")
    logger.info("Cleared REFERS_TO_PROCESS relations")


def upsert_term_to_step(
    client: OntologyClient, mappings: list[dict]
) -> int:
    """Term -[:REFERS_TO_PROCESS {role}]-> Step.

    같은 (Term, Step) 쌍은 한 번만 만들고 role을 갱신.
    """
    statements: list[tuple[str, dict]] = []
    for m in mappings:
        role = m["role"]
        if role not in ALLOWED_ROLES:
            raise ValueError(
                f"Disallowed REFERS_TO_PROCESS role: {role!r} "
                f"(allowed: {sorted(ALLOWED_ROLES)})"
            )
        statements.append(
            (
                "MATCH (t:Term {id: $term_id}) "
                "WITH t "
                "MATCH (s:Step {step_number: $step_num}) "
                "MERGE (t)-[r:REFERS_TO_PROCESS]->(s) "
                "SET r.role = $role",
                {
                    "term_id": m["term"],
                    "step_num": m["step_number"],
                    "role": role,
                },
            )
        )
    client.write_tx(statements)
    logger.info("Upserted %d REFERS_TO_PROCESS relations", len(mappings))
    return len(mappings)


def build_layer1_to_layer2(client: OntologyClient | None = None) -> dict[str, int]:
    own_client = client is None
    client = client or get_client()
    try:
        seed = load_seed()
        clear_layer1_to_layer2(client)
        n = upsert_term_to_step(client, seed["term_to_step"])
        counts = {"refers_to_process": n}
        logger.info("Bridge L1→L2 build complete: %s", counts)
        return counts
    finally:
        if own_client:
            close_client()


def _verify(client: OntologyClient, expected_total: int) -> None:
    """검증 쿼리 4 + 추가 무결성 체크."""
    print("\n=== 검증 쿼리 4: 'Edging' 키워드 → 어느 Step? ===")
    rows = client.query(
        "MATCH (:Term {korean_name: 'Edging'})-[:REFERS_TO_PROCESS]->(s:Step) "
        "RETURN s.step_number AS n, s.korean_name AS name "
        "ORDER BY s.step_number"
    )
    pretty = [(r["n"], r["name"]) for r in rows]
    print(f"'Edging' → {pretty}")
    assert [n for n, _ in pretty] == [2, 13], (
        f"Expected [2, 13], got {[n for n, _ in pretty]}"
    )

    print("\n=== 추가 검증: 관계 카운트 + role 분포 ===")
    rows = client.query(
        "MATCH ()-[r:REFERS_TO_PROCESS]->() RETURN count(r) AS n"
    )
    actual = rows[0]["n"]
    print(f"REFERS_TO_PROCESS 총 = {actual} (expected {expected_total})")
    assert actual == expected_total

    rows = client.query(
        "MATCH ()-[r:REFERS_TO_PROCESS]->() "
        "RETURN r.role AS role, count(r) AS n ORDER BY role"
    )
    print("role 분포:")
    for r in rows:
        print(f"  {r['role']}: {r['n']}")

    # 모든 role이 화이트리스트에 있는지
    roles = {r["role"] for r in rows}
    assert roles.issubset(ALLOWED_ROLES), f"Unexpected roles: {roles - ALLOWED_ROLES}"

    print("\n✅ Bridge L1→L2 검증 통과")


def match_method_to_step(method_name: str) -> int | None:
    """Stage 1 — 정규식 매칭으로 Step number 결정. 매치 없으면 None."""
    for pattern, step_num in METHOD_TO_STEP_PATTERNS:
        if re.search(pattern, method_name):
            return step_num
    return None


def clear_layer2_to_layer3(client: OntologyClient) -> None:
    """Layer 2↔3 Bridge 관계만 삭제. 노드는 보존."""
    client.write("MATCH (:Method)-[r:CALCULATES]->(:Step) DELETE r")
    client.write("MATCH (:Class)-[r:IMPLEMENTS]->(:Step) DELETE r")
    client.write("MATCH (:Class)-[r:RELATES_TO_STANDARD]->(:Standard) DELETE r")
    logger.info("Cleared Layer 2↔3 bridge relations")


def upsert_method_calculates_step(
    client: OntologyClient,
) -> tuple[int, list[str]]:
    """Stage 1 — 정규식 기반 :Method-[:CALCULATES]->:Step 생성.

    Returns:
        (생성된 관계 수, 매핑 안 된 calculate-* 메서드 이름 리스트)
    """
    rows = client.query(
        "MATCH (m:Method) "
        "RETURN m.id AS id, m.name AS name"
    )

    matched: list[tuple[str, int]] = []
    unmatched_calc: list[str] = []
    for r in rows:
        name = r["name"]
        step = match_method_to_step(name)
        if step is not None:
            matched.append((r["id"], step))
        elif name.startswith("calculate"):
            unmatched_calc.append(name)

    statements = [
        (
            "MATCH (m:Method {id: $method_id}) "
            "WITH m "
            "MATCH (s:Step {step_number: $step_num}) "
            "MERGE (m)-[:CALCULATES]->(s)",
            {"method_id": mid, "step_num": step},
        )
        for mid, step in matched
    ]
    if statements:
        client.write_tx(statements)
    logger.info(
        "Stage 1 정규식 매핑: %d Method-CALCULATES-Step (%d unmatched calculate-*)",
        len(matched),
        len(unmatched_calc),
    )
    return len(matched), unmatched_calc


def upsert_class_implements_step(client: OntologyClient) -> int:
    """Service 클래스가 자신의 메서드를 통해 :IMPLEMENTS Step.

    Method가 :CALCULATES Step이고, Class가 그 Method를 :CONTAINS하면
    Class -[:IMPLEMENTS]-> Step.
    """
    client.write(
        "MATCH (c:Class)-[:CONTAINS]->(m:Method)-[:CALCULATES]->(s:Step) "
        "MERGE (c)-[:IMPLEMENTS]->(s)"
    )
    rows = client.query(
        "MATCH ()-[r:IMPLEMENTS]->() RETURN count(r) AS n"
    )
    n = rows[0]["n"]
    logger.info("Class-IMPLEMENTS-Step: %d", n)
    return n


def upsert_form_relates_to_standard(client: OntologyClient) -> int:
    """Form 클래스 ↔ SC 기준 자동 매핑 (스펙 §E-2)."""
    statements: list[tuple[str, dict]] = []
    for class_name, code in FORM_TO_STANDARD.items():
        statements.append(
            (
                "MATCH (c:Class {name: $name}) "
                "WITH c "
                "MATCH (s:Standard {code: $code}) "
                "MERGE (c)-[:RELATES_TO_STANDARD]->(s)",
                {"name": class_name, "code": code},
            )
        )
    client.write_tx(statements)
    rows = client.query(
        "MATCH ()-[r:RELATES_TO_STANDARD]->() RETURN count(r) AS n"
    )
    n = rows[0]["n"]
    logger.info("Form-RELATES_TO_STANDARD: %d (expected %d)", n, len(FORM_TO_STANDARD))
    return n


def build_layer2_to_layer3(
    client: OntologyClient | None = None,
) -> dict[str, int | list[str]]:
    own_client = client is None
    client = client or get_client()
    try:
        clear_layer2_to_layer3(client)
        calc_count, unmatched = upsert_method_calculates_step(client)
        impl_count = upsert_class_implements_step(client)
        form_count = upsert_form_relates_to_standard(client)
        result: dict[str, int | list[str]] = {
            "calculates": calc_count,
            "implements": impl_count,
            "relates_to_standard": form_count,
            "unmatched_calculate_methods": unmatched,
        }
        logger.info("Bridge L2→L3 build complete: %s", {k: v for k, v in result.items() if k != "unmatched_calculate_methods"})
        return result
    finally:
        if own_client:
            close_client()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    client = get_client()
    try:
        l1_counts = build_layer1_to_layer2(client)
        print(f"\nL1→L2 counts: {l1_counts}")
        _verify(client, expected_total=l1_counts["refers_to_process"])

        l2_result = build_layer2_to_layer3(client)
        print(f"\nL2→L3 counts: {{'calculates': {l2_result['calculates']}, "
              f"'implements': {l2_result['implements']}, "
              f"'relates_to_standard': {l2_result['relates_to_standard']}}}")
        if l2_result["unmatched_calculate_methods"]:
            print(f"\n⚠️ Stage 1 매핑 안 된 calculate-* 메서드 ({len(l2_result['unmatched_calculate_methods'])}개):")
            for name in l2_result["unmatched_calculate_methods"]:
                print(f"  - {name}")

        # 검증 쿼리 6
        print("\n=== 검증 쿼리 6: 'Edging' Term → Step → Method → Class ===")
        rows = client.query(
            "MATCH (t:Term {korean_name: 'Edging'})"
            "      -[:REFERS_TO_PROCESS]->(s:Step)"
            "      <-[:CALCULATES]-(m:Method)"
            "      <-[:CONTAINS]-(c:Class) "
            "RETURN c.name AS class_name, m.name AS method_name, s.step_number AS step "
            "ORDER BY step, class_name, method_name"
        )
        if rows:
            print(f"  {len(rows)}개 결과:")
            for r in rows:
                print(f"    Step {r['step']:2d} ← {r['method_name']}() in {r['class_name']}")
        assert rows, "Expected ≥1 result for 검증 쿼리 6"
        print("\n✅ 검증 쿼리 6 통과")
    finally:
        close_client()


if __name__ == "__main__":
    main()
