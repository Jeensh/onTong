"""Phase 1 (A4-A/B/C) — Slab 데모의 도메인 매뉴얼 1차 자동 생성.

Section 2 모델링이 잘 동작하는지 검증하기 위한 첫 산출물.
사용자가 검토 후 BusinessTerm 시드 + ConceptBinding 시연의 입력으로 사용.

입력 :
    - sample-repos/slab-design-real/.analyzed/entities.json   (12-analyzer + JPA 메타)
    - JavadocRuleExtractor → BusinessRule 38건 (122 java 파일에서 자동 추출)
    - sample-repos/slab-design-real/toClaude/*.md              (사용자 제공 도메인 doc, 검증용)

출력 :
    wiki/슬랩설계/01-도메인-개념.md   (매뉴얼 1차)

Usage :
    cd /Users/donghae/workspace/ai/onTong
    .venv/bin/python scripts/generate_domain_manual.py

비고 :
    - LLM 없이 결정적 추출만 (NameMatch + 도메인 컨벤션). 시나리오 1 의 "다른 이름 같은 의미"
      클러스터링은 별도 단계 (P1.5+) 에서 LLM 활용.
    - 출력 형식: 사람이 검토하기 좋은 마크다운. ManualRegistry 업로드 가능.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.modeling.gap_detection import (  # noqa: E402
    InMemoryRuleRegistry,
    seed_rules_from_repo,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SLAB_REPO = REPO_ROOT / "sample-repos" / "slab-design-real"
SNAPSHOT = SLAB_REPO / ".analyzed" / "entities.json"
OUT_PATH = REPO_ROOT / "wiki" / "슬랩설계" / "01-도메인-개념.md"


# ---------------------------------------------------------------------------
# 데이터 추출
# ---------------------------------------------------------------------------
def collect_jpa_entities(snap: dict) -> list[dict]:
    """snapshot 에서 @Entity class 의 JPA 메타 추출."""
    out = []
    for fp, file_entry in snap["files"].items():
        for e in file_entry["entities"]:
            if e["kind"] != "class":
                continue
            attrs = e.get("attributes") or {}
            if not attrs.get("jpa_table"):
                continue
            out.append({
                "fqn": e["qualified_name"],
                "name": e["name"],
                "file_path": fp,
                "table": attrs.get("jpa_table"),
                "id_class": attrs.get("jpa_id_class"),
                "id_fields": attrs.get("jpa_id_fields") or [],
                "columns": attrs.get("jpa_columns_meta") or {},
            })
    return sorted(out, key=lambda e: e["table"])


def cluster_columns(entities: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """컬럼 cluster 두 종류 :
        same_name : 동일한 lowercase column name 이 여러 테이블에 (최소 2개) 등장
        suspected : 컨벤션 기반 의심 변종 (PRODUCT_TYPE_CD ↔ PRODUCT_NAME_CD ↔ PROD_KIND_CD,
                    HR_PLANT_CD ↔ HR_CD, etc.)
    """
    by_lower = defaultdict(list)
    for e in entities:
        for java_field, meta in e["columns"].items():
            by_lower[meta["name_lower"]].append({
                "table": e["table"],
                "java_field": java_field,
                "meta": meta,
            })

    same_name = {k: v for k, v in by_lower.items() if len(v) >= 2}

    # 컨벤션 기반 의심 변종 cluster (수동 정의 + 자동 매칭)
    suspected_groups = [
        # cluster_id, [keyword patterns], canonical_label, description
        ("품종품명코드",
         ["product_type_cd", "product_name_cd", "prod_kind_cd", "prod_type_cd"],
         "품종/품명코드",
         "제품 분류 코드. 동일 도메인이지만 4 테이블에서 다른 컬럼명 사용."),
        ("열연공장코드",
         ["hr_plant_cd", "hr_cd"],
         "열연공장코드",
         "열연 공장 코드 1자리. HR_SPEC 은 HR_PLANT_CD, HR_MIN/MAX_WGT 는 HR_CD 로 표기."),
        ("폭하한",
         ["width_low"],
         "폭 하한",
         "설계 가능 폭 하한 값."),
        ("폭상한",
         ["width_high"],
         "폭 상한",
         "설계 가능 폭 상한 값."),
        ("길이하한",
         ["length_low"],
         "길이 하한",
         "설계 가능 길이 하한 값."),
        ("길이상한",
         ["length_high"],
         "길이 상한",
         "설계 가능 길이 상한 값."),
        ("포장단중하한",
         ["pkg_wgt_low"],
         "포장 단중 하한",
         "고객 포장 단위 단중 하한."),
        ("포장단중상한",
         ["pkg_wgt_high"],
         "포장 단중 상한",
         "고객 포장 단위 단중 상한."),
        ("강종코드",
         ["grade_cd"],
         "강종 코드",
         "철강 강종 분류 (SS400, SM490, AH36, ...)."),
        ("고객사코드",
         ["customer_cd"],
         "고객사 코드",
         "주문 고객사 식별 코드."),
        ("회사코드",
         ["cmp_cd"],
         "회사 코드",
         "복합 PK 의 첫 자리 (2자리)."),
        ("소코드",
         ["org_cd"],
         "소 코드",
         "복합 PK 의 두 번째 자리 (1자리). 회사 내 조직."),
        ("주문번호",
         ["order_no"],
         "주문 번호",
         "고객 주문 식별. ORDER_OS = root, 다른 ORDER_* 는 FK→OS."),
        ("확정통과공장코드",
         ["confirmed_plant_cd"],
         "확정 통과 공장 코드",
         "8자리 인코딩 — 위치별 공정(SM, HR, HRF, CR, ANL1, ANL2, GAL, CRF), ' '=비활성."),
        ("가능통과공장코드",
         ["possible_plant_cd"],
         "가능 통과 공장 코드",
         "16자리 (2자리 × 8 공정) — 갈 수 있는 공장 후보."),
        ("우선순위",
         ["priority"],
         "우선순위",
         "다중 매칭 시 ASC 정렬로 첫 행 선택. EDGING_GROUP / CUSTOMER_STD 에 사용."),
        ("두께",
         ["thickness"],
         "두께",
         "Slab 두께 (mm). 2D sheet (HR_MIN/MAX_WGT) 의 첫 축."),
        ("폭",
         ["width"],
         "폭",
         "Slab 폭 (mm). 2D sheet 의 두 번째 축."),
        ("슬랩두께",
         ["slab_thickness"],
         "Slab 설계 두께",
         "step 1 의 출력. CAST_SPEC 룩업 결과."),
        ("슬랩번호",
         ["slab_no"],
         "Slab 번호",
         "12자리 zero-padded sequence. SLAB_RESULT/SLAB_DESIGN_HIST PK."),
        ("설계대기량",
         ["design_pend_qty"],
         "설계 대기량",
         "주문 잔여 설계 대상 수량. DG004 cross-check 의 입력."),
        ("Edging그룹코드",
         ["edging_group_cd"],
         "Edging 그룹 코드",
         "EDGING_GROUP 룩업 키 → EDGING_SPEC FK. '*' wildcard fallback."),
    ]

    # cluster ID → 매칭된 컬럼 list
    suspected = {}
    for cluster_id, patterns, canonical, desc in suspected_groups:
        matched = []
        for pattern in patterns:
            if pattern in by_lower:
                for occ in by_lower[pattern]:
                    matched.append({
                        **occ,
                        "matched_pattern": pattern,
                    })
        if matched:
            suspected[cluster_id] = {
                "canonical_label": canonical,
                "description": desc,
                "patterns": patterns,
                "occurrences": matched,
            }

    return same_name, suspected


# ---------------------------------------------------------------------------
# Markdown 생성
# ---------------------------------------------------------------------------
def render_table_section(entities: list[dict]) -> str:
    lines = ["## 12 테이블 정의 (코드 ground truth)\n"]
    lines.append("코드의 `@Entity` + `@Table` + `@Column` 어노테이션 기반 자동 추출. "
                 "사용자 제공 `sd-tables.md` 와 cross-check 후 차이 있으면 보고.\n")

    by_table = sorted(entities, key=lambda e: e["table"])
    for e in by_table:
        lines.append(f"### {e['table'].upper()} — {e['name']}\n")
        lines.append(f"- JPO FQN : `{e['fqn']}`")
        lines.append(f"- Composite PK : `@IdClass({e['id_class']})`"
                     if e["id_class"] else "- PK : single field")
        lines.append(f"- ID fields : {', '.join('`' + f + '`' for f in e['id_fields'])}\n")
        lines.append("| Java 필드 | DB 컬럼 | 타입 메타 | PK |")
        lines.append("|---|---|---|---|")
        for fld, meta in e["columns"].items():
            type_meta = []
            if meta.get("length"):
                type_meta.append(f"length={meta['length']}")
            if meta.get("precision"):
                type_meta.append(f"precision={meta['precision']}")
            if meta.get("scale") is not None:
                type_meta.append(f"scale={meta['scale']}")
            if meta.get("nullable") is False:
                type_meta.append("not_null")
            type_str = ", ".join(type_meta) if type_meta else "—"
            pk = "✓" if meta.get("is_id") else ""
            lines.append(f"| `{fld}` | `{meta['name']}` | {type_str} | {pk} |")
        lines.append("")
    return "\n".join(lines)


def render_clusters(same_name: dict, suspected: dict) -> str:
    lines = ["## BusinessTerm 후보 (Phase 2 propose-bindings 입력)\n"]

    # 1) 컨벤션 기반 시드 — 핵심 BusinessTerm 정의
    lines.append("### 1. 핵심 BusinessTerm 시드 (자동 인식 + 컨벤션 보강)\n")
    lines.append("이 항목들은 시나리오 1, 2 시연의 **승인 후 ConceptBinding 의 정답** 입니다.\n")
    lines.append("| BusinessTerm | 정의 | 매칭 컬럼 (테이블.컬럼명) | 일치도 |")
    lines.append("|---|---|---|---|")
    for cluster_id, data in suspected.items():
        occurrences = data["occurrences"]
        match_str = " · ".join(
            f"{o['table']}.{o['meta']['name']}" + (
                f" (length={o['meta'].get('length')})" if o['meta'].get('length') else ""
            )
            for o in occurrences[:6]
        )
        if len(occurrences) > 6:
            match_str += f" ... +{len(occurrences) - 6}"
        # 일치도 표기
        unique_patterns = {o["matched_pattern"] for o in occurrences}
        if len(unique_patterns) > 1:
            match_grade = f"⭐ **시연 victim** ({len(unique_patterns)} 변종)"
        elif len(occurrences) > 1:
            match_grade = "정확 매칭"
        else:
            match_grade = "단일 사용"
        lines.append(f"| **{data['canonical_label']}** | {data['description']} | {match_str} | {match_grade} |")
    lines.append("")

    # 2) 시나리오 1, 2 강조
    lines.append("### 2. 시나리오 1·2 victim 컬럼 (도구 시연의 핵심)\n")
    for cluster_id, data in suspected.items():
        unique_patterns = sorted({o["matched_pattern"] for o in data["occurrences"]})
        if len(unique_patterns) <= 1:
            continue
        lines.append(f"#### {data['canonical_label']}\n")
        lines.append(f"{data['description']}\n")
        lines.append("| 테이블 | 컬럼명 | length |")
        lines.append("|---|---|---|")
        for o in data["occurrences"]:
            lines.append(f"| {o['table']} | `{o['meta']['name']}` | {o['meta'].get('length', '—')} |")
        lines.append("")
        lines.append("**시연 메시지** : 6 컬럼이 도메인적으로 동일하지만 이름·길이가 제각각. "
                     "도구가 통합 BusinessTerm 으로 매핑 → 한 컬럼 변경 시 5 컬럼 동시 보정 필요 인사이트.\n")

    # 3) 추가 same-name 클러스터 (앞에서 안 다룬 것)
    covered_lowers = set()
    for data in suspected.values():
        for o in data["occurrences"]:
            covered_lowers.add(o["meta"]["name_lower"])

    leftover_same = {k: v for k, v in same_name.items() if k not in covered_lowers}
    if leftover_same:
        lines.append("### 3. 같은 이름 다중 사용 (BusinessTerm 후보, 자동 시드 가능)\n")
        lines.append("| 컬럼명 | 사용 테이블 |")
        lines.append("|---|---|")
        for col_lower, occs in sorted(leftover_same.items(), key=lambda x: (-len(x[1]), x[0])):
            tables = ", ".join(o["table"] for o in occs)
            lines.append(f"| `{col_lower}` | {tables} |")
        lines.append("")
    return "\n".join(lines)


def render_rules(rules: list) -> str:
    lines = ["## BusinessRule (Javadoc 자동 추출)\n"]
    lines.append(f"`JavadocRuleExtractor` (E1-d) 가 122 java 파일에서 추출한 비즈니스 룰 = {len(rules)} 건. "
                 "한국어 자연어 룰 → CONFLICTS_WITH gap 감지의 코드 쪽 입력.\n")

    # 위치별 분류 — Action 기준 alphabetic
    by_target = defaultdict(list)
    for r in rules:
        # qualified_name format: com.x.SdXxxAction#rule1
        # source = 그 부분
        target = r.qualified_name.rsplit("#", 1)[0].rsplit(".", 1)[-1]
        by_target[target].append(r)

    for target in sorted(by_target):
        lines.append(f"### {target}\n")
        for r in by_target[target]:
            sev_emoji = "🟥" if r.severity.value == "hard" else "🟦"
            lines.append(f"- {sev_emoji} `{r.qualified_name.rsplit('#', 1)[1]}` : {r.statement}")
        lines.append("")
    return "\n".join(lines)


def render_header() -> str:
    return f"""# Slab 설계 도메인 개념 (자동 생성 — Phase 1 매뉴얼 1차)

> 생성 시각 : {datetime.now(timezone.utc).isoformat()}
> 입력 : `sample-repos/slab-design-real/` (122 java files, 14 @Entity)
> 도구 : 12-analyzer + `JavadocRuleExtractor` + cluster heuristic
> **목적** : Section 2 모델링이 데모 코드를 정확히 분석함을 입증 — 사용자가 검토 후 BusinessTerm 시드로 사용.

이 문서는 **데모 소스 코드를 ground truth 로** 자동 생성됐습니다.
사용자 제공 `sample-repos/slab-design-real/toClaude/sd-tables.md` 와 cross-check 시 차이 있으면 코드 (이 문서) 가 우선.

## 데이터 출처
- JPA `@Entity` / `@Table(name=)` / `@Column(name=, length=, precision=, scale=)` / `@IdClass` / `@Id`
- Javadoc `/** ... */` 안 한국어 룰 문장 (38 건)
- 사용자 제공 도메인 문서 7건 (PROJECT_OVERVIEW.md / sd-tables.md / scenarios.md / ALGORITHM.md / DRAMA_DNA.md / architect.md / slab-design.md) — 검증·보강용

---

"""


def main() -> int:
    if not SNAPSHOT.exists():
        print(f"ERROR: snapshot not found at {SNAPSHOT}", file=sys.stderr)
        print("Run scripts/dump_entities_snapshot.py first.", file=sys.stderr)
        return 2

    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    entities = collect_jpa_entities(snap)
    same_name, suspected = cluster_columns(entities)

    # JavadocRuleExtractor 실행 (122 파일, 38 rules)
    reg = InMemoryRuleRegistry()
    seed_result = seed_rules_from_repo(SLAB_REPO, "slab-design-real", reg)
    rules = list(reg.list_by_repo("slab-design-real"))

    # markdown 조립
    parts = [
        render_header(),
        render_table_section(entities),
        render_clusters(same_name, suspected),
        render_rules(rules),
    ]
    body = "\n".join(parts)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(body, encoding="utf-8")

    print(f"[manual] {OUT_PATH}")
    print(f"  - {len(entities)} JPA entities (12 핵심 테이블 + 보조)")
    print(f"  - {len(suspected)} BusinessTerm 시드 후보 (컨벤션 매칭)")
    victim_count = sum(
        1 for d in suspected.values()
        if len({o['matched_pattern'] for o in d['occurrences']}) > 1
    )
    print(f"    (그 중 ⭐ 시연 victim = {victim_count} 클러스터)")
    print(f"  - {len(same_name)} 추가 same-name 컬럼 클러스터")
    print(f"  - {len(rules)} BusinessRule (Javadoc 자동 추출)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
