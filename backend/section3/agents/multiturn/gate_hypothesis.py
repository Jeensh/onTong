"""Phase 13c — executed_hypothesis builder.

hypothesis intent 응답. "X 가 Y 이면 어떻게?" 같은 boundary 질의에 대해 body +
business_rules 를 evidence 로 verdict (yes/no/likely_*/unknown) 회신.

verdict heuristic (Phase 13c MVP):
  1) body 의 token 매칭 (var + value/op 가 body 안에 있는지)
  2) business_rules.statement 안에 var + value 가 있는지
  3) 둘 다 있으면 likely_yes / 한 쪽이면 likely_yes (단 confidence 차등)
  4) 아무것도 없으면 unknown
  5) 향후 (Phase 13d): fixture synthesis 로 실제 실행 검증 + LLM 추론으로 확신도

최QA 페르소나 1:1 해결 (boundary value 추론 + Q5 "확실한 근거").
"""
from __future__ import annotations

import asyncio
import logging

from .integrity_warning_kinds import emit_warning
from .ontology_client import OntologyClient
from .schemas import (
    ActionRef,
    BusinessRuleEvidence,
    GateExecutedHypothesis,
    HypothesisVerdict,
    Provenance,
)

logger = logging.getLogger(__name__)


async def build_gate_hypothesis(
    *,
    target: ActionRef,
    conditions: list[dict[str, str]],
    repo_id: str,
    ontology_client: OntologyClient,
) -> GateExecutedHypothesis:
    """target 의 body + business_rules 로 hypothesis verdict 추론."""

    body_task = ontology_client.get_method_body(
        target.code_method_fqn, repo_id=repo_id,
    )
    meta_task = (
        ontology_client.get_method_meta(target.code_method_fqn, repo_id=repo_id)
        if hasattr(ontology_client, "get_method_meta") else _noop_meta()
    )
    body, meta = await asyncio.gather(body_task, meta_task)

    body_text = body or ""
    file_path = (meta or {}).get("file_path") or (
        target.location.file_path if target.location else ""
    )
    line_start = int((meta or {}).get("line_start") or (
        target.location.line_start if target.location else 0
    ))
    line_end = int((meta or {}).get("line_end") or (
        target.location.line_end if target.location else 0
    ))

    linked_action_label, linked_term = await asyncio.to_thread(
        _fetch_action_meta, target.action_id, repo_id,
    )
    evidence = await asyncio.to_thread(
        _fetch_rule_evidence, linked_term, repo_id,
    )

    # Phase 14B (MVP) — fixture compatibility 사전 체크 (실 fixture 실행 X)
    # Phase 16A — repo_id 전달 → 한·영 alias bridge 활성화
    params = await _fetch_method_params(fqn=target.code_method_fqn, repo_id=repo_id)
    fixture_compat = _check_fixture_compat(
        conditions=conditions, params=params, repo_id=repo_id,
    )

    # Phase 14F (MVP) — fragment-level anchor_bindings surface (read-only visibility +
    # var ↔ target_slot 매칭 시 rule_signals 보강).
    anchor_bindings = await asyncio.to_thread(
        _fetch_anchor_bindings, fqn=target.code_method_fqn, repo_id=repo_id,
    )
    # condition var 가 anchor.target_slot 또는 rationale 과 매칭하면 anchor_signals +1
    anchor_signals = 0
    matched_anchor_slots: list[str] = []
    for cond in conditions:
        var = (cond.get("var") or "").strip().lower()
        if not var:
            continue
        for ab in anchor_bindings:
            slot_lower = (ab["target_slot"] or "").lower()
            rationale_lower = (ab["rationale"] or "").lower()
            if (
                slot_lower and (var in slot_lower or slot_lower in var)
            ) or (rationale_lower and var in rationale_lower):
                anchor_signals += 1
                if ab["target_slot"]:
                    matched_anchor_slots.append(ab["target_slot"])
                break  # 한 var 당 한 번만 카운트

    # Phase 16B — condition 별 한·영 alias list 추출 (asyncio.to_thread)
    var_aliases_per_cond: list[list[str]] = []
    for cond in conditions:
        var = (cond.get("var") or "").strip()
        if not var:
            var_aliases_per_cond.append([])
            continue
        aliases = await asyncio.to_thread(
            _expand_var_to_aliases, var=var, repo_id=repo_id,
        )
        var_aliases_per_cond.append(aliases)

    verdict, reasoning, body_signals, rule_signals = _infer_verdict(
        body_text=body_text, conditions=conditions, evidence=evidence,
        var_aliases_per_cond=var_aliases_per_cond,
    )

    # Phase 14B — fixture_compat 결과로 verdict 보정:
    #   - compat=True 면 verdict 강화 (likely_yes → yes)
    #   - compat=False + type incompat 면 verdict 약화 (heuristic 가 type 잘못 추론)
    #   - compat=False + var miss → verdict 영향 안 줌 (Korean↔English alias 미고려
    #     로 인한 false negative 위험. provenance 에 경고만 surface)
    # Phase 16F QA fix — multi-cond partial OR zero match 인 경우 yes 승격 금지
    # reasoning 의 "partial" / "0/N 매칭" / "1/N 매칭" 등 (M/N where M<N) detect
    import re as _re_pmc
    is_partial_multi_cond = bool(
        "partial" in reasoning.lower()
        or _re_pmc.search(r"조건 (\d+)/(\d+)", reasoning)
        and (lambda m: int(m.group(1)) < int(m.group(2)))(
            _re_pmc.search(r"조건 (\d+)/(\d+)", reasoning),
        )
    )
    if fixture_compat["compat"] is True:
        if verdict == "likely_yes" and not is_partial_multi_cond:
            verdict = "yes"
            reasoning = (
                f"{reasoning} · fixture-compat 통과 (matched params: "
                f"{fixture_compat['matched_params']})"[:400]
            )
        elif verdict == "likely_yes" and is_partial_multi_cond:
            # partial 인 경우 boost 안 함, 정보는 surface
            reasoning = (
                f"{reasoning} · fixture-compat 통과 but partial multi-cond — "
                f"verdict yes 승격 보류"
            )[:400]
    elif fixture_compat["compat"] is False:
        # var miss vs type incompat 구분
        reason = fixture_compat["mismatch_reason"] or ""
        is_type_incompat = "type" in reason.lower() and "불일치" in reason
        if is_type_incompat and verdict in ("yes", "likely_yes"):
            verdict = "likely_no"
            reasoning = (
                f"{reasoning} · 그러나 fixture-compat 실패 (type 불일치): "
                f"{reason}"[:400]
            )
        # var miss 는 verdict 영향 안 줌 — sources 에 경고만 (한·영 alias 미커버)

    # confidence: signals 가 강할수록 high. Phase 14F — anchor_signals 도 합산.
    signal_count = body_signals + rule_signals + anchor_signals * 2  # anchor 가중 ×2
    if verdict == "unknown":
        confidence = 0.2
    elif signal_count >= 4:
        confidence = 0.85
    elif signal_count >= 2:
        confidence = 0.75
    elif signal_count == 1:
        confidence = 0.55
    else:
        confidence = 0.35

    sources: list[Provenance] = [
        Provenance(
            source="ontology",
            detail=(
                f"executed_hypothesis method={target.code_method_fqn} "
                f"conds={len(conditions)} body_signals={body_signals} "
                f"rule_signals={rule_signals}"
            )[:500],
            confidence=1.0 if body_text else 0.0,
        ),
    ]
    if evidence:
        sources.append(Provenance(
            source="ontology",
            detail=f"business_rules {len(evidence)} 행 evidence",
            confidence=1.0,
        ))
    # Phase 14F — anchor_bindings surface
    if anchor_bindings:
        anchor_detail = (
            f"anchor_bindings {len(anchor_bindings)} 행 (fragment-level mapping)"
        )
        if matched_anchor_slots:
            anchor_detail += (
                f" · matched slots: {sorted(set(matched_anchor_slots))[:5]}"
            )
        sources.append(Provenance(
            source="ontology",
            detail=anchor_detail[:500],
            confidence=0.92 if matched_anchor_slots else 0.7,
        ))

    # Phase 14B — fixture_compat 결과 surface
    if fixture_compat["compat"] is not None:
        compat_str = "ok" if fixture_compat["compat"] else "fail"
        compat_detail = (
            f"fixture_compat={compat_str} "
            f"matched_params={fixture_compat['matched_params']}"
        )
        if fixture_compat["mismatch_reason"]:
            compat_detail += f" reason={fixture_compat['mismatch_reason']}"
        sources.append(Provenance(
            source="sim_v2",
            detail=compat_detail[:500],
            confidence=0.8 if fixture_compat["compat"] else 0.3,
        ))
    sources.append(Provenance(
        source="llm_inference",
        detail=(
            f"verdict={verdict!r} reasoning={reasoning!r}"
        )[:500],
        confidence=confidence,
    ))

    # Phase 16C/D — verdict-fixture cross-check integrity warnings
    # matched_var 는 reasoning 의 `(matched var='...')` 패턴에서 추출
    import re as _re_post
    mv_match = _re_post.search(r"matched var='([^']*)'", reasoning)
    matched_var_for_check = mv_match.group(1) if mv_match else ""
    integrity_warnings = _compute_integrity_warnings(
        verdict=verdict,
        reasoning=reasoning,
        body_signals=body_signals,
        rule_signals=rule_signals,
        fixture_compat=fixture_compat,
        matched_var=matched_var_for_check,
        target_fqn=target.code_method_fqn,
    )
    for w in integrity_warnings:
        sources.append(Provenance(
            source="llm_inference",
            detail=w[:500],
            confidence=0.5,  # warning 자체의 confidence
        ))

    return GateExecutedHypothesis(
        target=target,
        conditions=conditions,
        body_text=body_text,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        verdict=verdict,
        reasoning=reasoning,
        evidence=evidence,
        confidence=confidence,
        sources=sources,
    )


async def _noop_meta():
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 16C — verdict-fixture cross-check assertion
# ─────────────────────────────────────────────────────────────────────────────


_BODY_UNSUPPORTED_PHRASES = (
    "변수 매칭 없음", "변수 매칭 약함", "조건 활성 판단 불가",
    "rule 기반 추정", "다른 method 일 가능성",
)


def _compute_integrity_warnings(
    *,
    verdict: str,
    reasoning: str,
    body_signals: int,
    rule_signals: int,
    fixture_compat: dict,
    matched_var: str | None = None,
    target_fqn: str = "",
) -> list[str]:
    """verdict / reasoning / signals / fixture_compat 의 cross-consistency 체크.

    반환: warning string list. 빈 list 면 일관 (정상).

    Phase 16B 시니어 TOP 권고: W1 / W1b / W2 / W3.
    Phase 16D QA 권고: W1c (alias_gap root cause) + W4 (target_is_test).
    """
    warnings: list[str] = []
    verdict = (verdict or "").lower()
    reasoning_lower = (reasoning or "").lower()
    compat = fixture_compat.get("compat") if fixture_compat else None
    compat_reason = (fixture_compat.get("mismatch_reason") if fixture_compat else "") or ""
    is_var_miss = "var" in compat_reason.lower() and (
        "매칭 안 됨" in compat_reason or "miss" in compat_reason.lower()
    )

    # W1: verdict=yes/likely_yes 인데 body 자체는 unsupported (rule 기반 추정 또는 자백)
    if verdict in ("yes", "likely_yes"):
        body_unsupported = any(
            phrase in reasoning for phrase in _BODY_UNSUPPORTED_PHRASES
        )
        if body_unsupported and rule_signals == 0:
            warnings.append(emit_warning(
                "body_unsupported_no_rule",
                f"verdict={verdict} 인데 reasoning 이 변수 매칭 없음 + rule 0",
            ))
        elif body_unsupported and rule_signals >= 1:
            # rule 기반 추정 — 약한 warning (의도된 fallback)
            warnings.append(emit_warning(
                "body_unsupported_rule_only",
                f"verdict={verdict} 가 rule {rule_signals} 행 기반 추정. body 직접 검증 X",
            ))

    # W2: likely_yes 인데 fixture compat=fail + rule_signals=0 → no evidence
    if verdict in ("yes", "likely_yes"):
        if compat is False and rule_signals == 0 and body_signals < 2:
            # 모든 evidence 약함
            if not any("body_unsupported" in w for w in warnings):
                warnings.append(emit_warning(
                    "no_strong_evidence",
                    f"verdict={verdict} 인데 fixture_compat=fail + rule=0 + body 약함",
                ))

    # W3: likely_no / no 인데 body_signals 가 강하거나 fixture_compat=ok
    if verdict in ("likely_no", "no"):
        if compat is True and body_signals >= 3:
            warnings.append(emit_warning(
                "cross_evidence_mismatch",
                f"verdict={verdict} 인데 fixture_compat=ok + body_signals={body_signals} "
                "강함 — verdict 가 약하게 추정됨",
            ))

    # Phase 16D — W1c: alias_gap root cause (QA 권고)
    # matched_var=None 면 unset (호출자가 미전달) — W1c 미발화.
    # matched_var=="" 명시적 빈 값 + rule≥2 → alias_gap warning.
    if verdict in ("yes", "likely_yes") and matched_var == "":
        if rule_signals >= 2:
            warnings.append(emit_warning(
                "body_unsupported_alias_gap",
                f"verdict={verdict}: matched_var=빈 값 + rule {rule_signals} 행 기반. "
                "Korean↔English alias 가 추가로 필요할 가능성",
            ))

    # Phase 16D — W4: target_is_test (QA 권고)
    if target_fqn:
        target_lower = target_fqn.lower()
        is_test = any(
            pat in target_lower for pat in ("test.", "test(", "stub.", "stub(")
        ) or "tests." in target_lower or target_lower.endswith("test")
        is_mock = "mock" in target_lower
        if is_test or is_mock:
            warnings.append(emit_warning(
                "target_is_test",
                f"target {target_fqn!r} 가 Test/Mock 패턴 — ranking 이 production "
                "code 대신 테스트/모킹 클래스를 선택했을 가능성",
            ))

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Phase 14B (MVP) — fixture compatibility check
# ─────────────────────────────────────────────────────────────────────────────


_NUMERIC_TYPES = {"int", "long", "short", "byte", "integer"}
_DECIMAL_TYPES = {"double", "float", "bigdecimal", "decimal"}
_STRING_TYPES = {"string", "char", "character"}
_BOOL_TYPES = {"boolean", "bool"}


def _normalize_type(t: str) -> str:
    """Java/Python type 을 lowercase + 기본형으로 정규화."""
    if not t:
        return ""
    s = t.strip().lower()
    # Generic / array 제거 (`List<X>` → `list`)
    for ch in "<>[]":
        if ch in s:
            s = s.split(ch, 1)[0]
    return s.strip()


def _value_type_kind(value: str) -> str:
    """value 의 type 추론 — int / decimal / string / bool / unknown."""
    if not value:
        return "unknown"
    s = value.strip()
    if s.lower() in ("true", "false"):
        return "bool"
    try:
        int(s)
        return "int"
    except ValueError:
        pass
    try:
        float(s)
        return "decimal"
    except ValueError:
        pass
    return "string"


def _types_compatible(value_kind: str, param_type_norm: str) -> bool:
    """value kind 와 param type 의 호환성.

    decimal value → numeric param OK (값 정밀도 손실 가능, 단 매칭은 valid).
    int value → decimal param OK (widening).
    string value → string param 만 OK.
    bool value → bool param 만 OK.
    decimal value → int param X (narrowing, 부정확).
    """
    if param_type_norm in _NUMERIC_TYPES:
        return value_kind in ("int",)
    if param_type_norm in _DECIMAL_TYPES:
        return value_kind in ("int", "decimal")
    if param_type_norm in _STRING_TYPES:
        return value_kind in ("string", "int", "decimal")
    if param_type_norm in _BOOL_TYPES:
        return value_kind == "bool"
    # unknown param type → 보수적으로 compat=True (모름)
    return True


_COLUMN_NAME_RE = __import__("re").compile(r"@Column\([^)]*\bname=([A-Za-z0-9_]+)")


def _expand_var_to_aliases(
    *,
    var: str,
    repo_id: str | None,
) -> list[str]:
    """Phase 16A + 16G — condition var 의 한·영 alias 확장 (3 source union).

    Source 우선순위:
      1. `BusinessTermRow.aliases_json` (16A) — domain 의 정식 한·영 매핑
      2. `ActionRow.aliases_json` (16G) — action 레벨 alias (BusinessTerm 미커버 보강)
      3. `CodeFieldRow` `@Column(name=XXX)` (16G) — Java field name ↔ DB column 양방향

    모든 source 는 **strict 정확 매칭** (label/alias 가 lookup 과 정확히 같음).
    var token-level expansion: "주문 수량" → ["주문 수량", "주문", "수량"] 각각 시도.

    repo_id=None 이면 원본만 반환 (backward compat).
    """
    base = [var]
    if not repo_id or not var:
        return base
    var_lower = var.lower()
    # token-level lookup candidates
    lookup_candidates = [var]
    for tok in var.split():
        tok = tok.strip()
        if tok and tok.lower() != var_lower and tok not in lookup_candidates:
            lookup_candidates.append(tok)

    try:
        import json as _json
        from sqlalchemy import select as _select, or_
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessTermRow
        from backend.modeling.mapping_layer.orm import ActionRow
        from backend.modeling.code_layer.orm import CodeFieldRow, CodeTypeRow

        out = list(base)
        # case-preserving dedup — "thickness" vs "THICKNESS" 는 distinct alias
        # (e.g., Java field vs DB column 이름) — exact string 기준
        out_set: set[str] = {var}

        def _add_alias(s: str) -> None:
            if s and s not in out_set:
                out.append(s)
                out_set.add(s)

        def _absorb_label_aliases(label: str, alias_strs: list[str], lookup_lower: str) -> None:
            if (
                label.lower() == lookup_lower
                or any(a.lower() == lookup_lower for a in alias_strs)
            ):
                _add_alias(label)
                for a in alias_strs:
                    _add_alias(a)

        for lookup in lookup_candidates:
            lookup_lower = lookup.lower()
            with session_scope() as s:
                # (1) BusinessTerm
                bt_rows = s.execute(
                    _select(BusinessTermRow).where(
                        BusinessTermRow.repo_id == repo_id,
                        or_(
                            BusinessTermRow.label.like(f"%{lookup}%"),
                            BusinessTermRow.aliases_json.like(f"%{lookup}%"),
                        ),
                    ).limit(20),
                ).scalars().all()
                for r in bt_rows:
                    label = (r.label or "").strip()
                    try:
                        aliases = _json.loads(r.aliases_json or "[]")
                    except Exception:  # noqa: BLE001
                        aliases = []
                    _absorb_label_aliases(
                        label, [str(a).strip() for a in aliases], lookup_lower,
                    )

                # (2) 16G — Action.aliases_json
                act_rows = s.execute(
                    _select(ActionRow).where(
                        ActionRow.repo_id == repo_id,
                        or_(
                            ActionRow.label.like(f"%{lookup}%"),
                            ActionRow.aliases_json.like(f"%{lookup}%"),
                        ),
                    ).limit(20),
                ).scalars().all()
                for a_row in act_rows:
                    label = (a_row.label or "").strip()
                    try:
                        aliases = _json.loads(a_row.aliases_json or "[]")
                    except Exception:  # noqa: BLE001
                        aliases = []
                    _absorb_label_aliases(
                        label, [str(a).strip() for a in aliases], lookup_lower,
                    )

                # (3) 16G — CodeField @Column(name=XXX) bidirectional bridge
                # Java field name ↔ DB column 이름 매칭
                cf_rows = s.execute(
                    _select(CodeFieldRow, CodeTypeRow.repo_id)
                    .join(CodeTypeRow, CodeFieldRow.type_fqn == CodeTypeRow.fqn)
                    .where(
                        CodeTypeRow.repo_id == repo_id,
                        or_(
                            CodeFieldRow.name == lookup,
                            CodeFieldRow.annotations_json.like(f"%name={lookup}%"),
                            CodeFieldRow.annotations_json.like(f"%name={lookup},%"),
                        ),
                    ).limit(20),
                ).all()
                for cf_tuple in cf_rows:
                    cf = cf_tuple[0]
                    fname = (cf.name or "").strip()
                    col_name: str | None = None
                    for ann_str in _json.loads(cf.annotations_json or "[]"):
                        if not isinstance(ann_str, str):
                            continue
                        m = _COLUMN_NAME_RE.search(ann_str)
                        if m:
                            col_name = m.group(1)
                            break
                    if not col_name:
                        continue
                    # bidirectional: lookup 이 field name OR column name 과 일치하면
                    # 양쪽 모두 alias 로 추가
                    if (
                        fname.lower() == lookup_lower
                        or col_name.lower() == lookup_lower
                    ):
                        _add_alias(fname)
                        _add_alias(col_name)
        return out
    except Exception as e:  # noqa: BLE001
        logger.debug("_expand_var_to_aliases 실패 (graceful): %s", e)
        return base


def _check_fixture_compat(
    *,
    conditions: list[dict[str, str]],
    params: list[dict[str, str]],
    repo_id: str | None = None,
) -> dict:
    """conditions 가 method params 와 fixture-ready 인지 사전 체크.

    Phase 14B (MVP) — 실 fixture 실행 X. 단순 type-compat 만:
      - var 가 어떤 param name 과 substring 매칭하는가?
      - 매칭한 param 의 type 이 condition value 의 type 과 compat 한가?

    Phase 16A — `repo_id` 옵셔널: 전달 시 한·영 alias 확장 (business_terms.aliases_json
    정확 매칭) 후 param 매칭 시도. 14B 시니어 검증 false negative 해결.

    반환: {"compat": True/False/None, "matched_params": [...], "mismatch_reason": str}
    """
    if not conditions or not params:
        return {"compat": None, "matched_params": [], "mismatch_reason": ""}

    matched: list[str] = []
    incompat_reasons: list[str] = []
    var_misses: list[str] = []

    for cond in conditions:
        var = (cond.get("var") or "").strip()
        value = (cond.get("value") or "").strip()
        op = (cond.get("op") or "").strip()
        if not var or not value:
            continue

        # Phase 16A — var 의 한·영 alias 확장 (repo_id 있을 때만)
        var_candidates = _expand_var_to_aliases(var=var, repo_id=repo_id)

        matched_param: dict[str, str] | None = None
        for candidate_var in var_candidates:
            cv_tokens = [t.strip().lower() for t in candidate_var.split() if t.strip()]
            cv_compact = "".join(cv_tokens)
            cv_lower = candidate_var.lower()
            for p in params:
                pname_lower = (p.get("name") or "").lower()
                if not pname_lower:
                    continue
                if (
                    cv_lower in pname_lower
                    or pname_lower in cv_lower
                    or (cv_compact and (cv_compact in pname_lower
                                        or pname_lower in cv_compact))
                    or (cv_tokens and all(t in pname_lower for t in cv_tokens))
                ):
                    matched_param = p
                    break
            if matched_param is not None:
                break

        if matched_param is None:
            var_misses.append(var)
            continue

        # Type compat 체크
        param_type = _normalize_type(matched_param.get("type") or "")
        value_kind = _value_type_kind(value)
        if param_type and not _types_compatible(value_kind, param_type):
            incompat_reasons.append(
                f"value {value!r} (type={value_kind}) 가 param "
                f"{matched_param.get('name')!r} (type={param_type!r}) 와 type 불일치",
            )
            continue
        matched.append(matched_param.get("name") or "")

    if not matched and not incompat_reasons:
        # 모든 var 가 param 과 매칭 안 됨
        return {
            "compat": False,
            "matched_params": [],
            "mismatch_reason": (
                f"var {var_misses} 가 어떤 method param 과도 매칭 안 됨 — "
                f"다른 method 가설일 가능성"
            ),
        }
    if incompat_reasons:
        return {
            "compat": False,
            "matched_params": matched,
            "mismatch_reason": "; ".join(incompat_reasons),
        }
    return {
        "compat": True,
        "matched_params": matched,
        "mismatch_reason": "",
    }


def _fetch_anchor_bindings(
    *,
    fqn: str,
    repo_id: str,
) -> list[dict]:
    """Phase 14F — code_method 의 anchor_bindings (fragment-level mapping) fetch.

    `mapping_layer.AnchorBindingRow` 의 행: anchor_locator / target_action_fqn /
    target_slot / confidence / rationale / line / confirmed / source.

    이미 modeling 측에 시드된 fragment-level mapping (slab-design-real-v2 기준
    163 행) 을 multiturn agent 가 surface — substring 매칭이 잡지 못하는 AST-level
    code↔action 매핑을 verdict / 사용자에게 노출.

    실패 graceful — 빈 list 반환.
    """
    try:
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.mapping_layer.orm import AnchorBindingRow

        with session_scope() as s:
            rows = s.execute(
                _select(AnchorBindingRow).where(
                    AnchorBindingRow.code_method_fqn == fqn,
                    AnchorBindingRow.repo_id == repo_id,
                ).order_by(AnchorBindingRow.line.asc()),
            ).scalars().all()
        return [
            {
                "id": r.id,
                "anchor_locator": r.anchor_locator,
                "target_action_fqn": r.target_action_fqn,
                "target_slot": r.target_slot or "",
                "confidence": float(r.confidence or 0.0),
                "rationale": r.rationale or "",
                "line": int(r.line or 0),
                "confirmed": bool(r.confirmed),
                "source": r.source or "",
            }
            for r in rows
        ]
    except Exception as e:  # noqa: BLE001
        logger.debug("_fetch_anchor_bindings 실패 (graceful): %s", e)
        return []


async def _fetch_method_params(
    *,
    fqn: str,
    repo_id: str,
) -> list[dict[str, str]]:
    """method params (name + type) 를 SQLite 에서 fetch.

    실패 graceful — 빈 list 반환.
    """
    def _run() -> list[dict[str, str]]:
        try:
            import json as _json
            from sqlalchemy import select as _select
            from backend.modeling.persistence.database import session_scope
            from backend.modeling.code_layer.orm import CodeMethodRow

            with session_scope() as s:
                row = s.execute(
                    _select(CodeMethodRow).where(
                        CodeMethodRow.fqn == fqn,
                        CodeMethodRow.repo_id == repo_id,
                    ),
                ).scalar_one_or_none()
            if row is None or not row.params_json:
                return []
            try:
                parsed = _json.loads(row.params_json)
            except Exception:  # noqa: BLE001
                return []
            out: list[dict[str, str]] = []
            for p in parsed if isinstance(parsed, list) else []:
                if isinstance(p, dict):
                    out.append({
                        "name": str(p.get("name") or ""),
                        "type": str(p.get("type") or ""),
                    })
            return out
        except Exception as e:  # noqa: BLE001
            logger.debug("_fetch_method_params 실패 (graceful): %s", e)
            return []
    return await asyncio.to_thread(_run)


def _fetch_action_meta(
    action_id: str, repo_id: str,
) -> tuple[str | None, str | None]:
    try:
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.mapping_layer.orm import ActionRow

        with session_scope() as s:
            row = s.execute(
                _select(ActionRow).where(
                    ActionRow.fqn == action_id,
                    ActionRow.repo_id == repo_id,
                ),
            ).scalar_one_or_none()
        if row is None:
            return None, None
        return (row.label or None, row.declared_on_term or None)
    except Exception as e:  # noqa: BLE001
        logger.debug("_fetch_action_meta 실패: %s", e)
        return None, None


def _fetch_rule_evidence(
    linked_term: str | None, repo_id: str,
) -> list[BusinessRuleEvidence]:
    if not linked_term:
        return []
    try:
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessRuleRow

        with session_scope() as s:
            rows = s.execute(
                _select(BusinessRuleRow).where(
                    BusinessRuleRow.repo_id == repo_id,
                    BusinessRuleRow.terms_ref_json.like(f"%{linked_term}%"),
                ),
            ).scalars().all()
        return [
            BusinessRuleEvidence(
                fqn=r.fqn,
                statement=r.statement,
                severity=r.severity,
            )
            for r in rows[:10]
        ]
    except Exception as e:  # noqa: BLE001
        logger.debug("_fetch_rule_evidence 실패: %s", e)
        return []


def _infer_verdict(
    *,
    body_text: str,
    conditions: list[dict[str, str]],
    evidence: list[BusinessRuleEvidence],
    var_aliases_per_cond: list[list[str]] | None = None,
) -> tuple[HypothesisVerdict, str, int, int]:
    """body + business_rules 에서 conditions 시그널 추출 (Phase 14D 정밀화).

    리턴: (verdict, reasoning, body_signals_count, rule_signals_count).

    Phase 14D 개선 (이전 heuristic 의 false positive 해결):
      (a) var token AND 매칭 — 다중 단어 var ("주문 수량") 의 모든 token 등장 시만 hit
      (b) value word-boundary 매칭 — "0" 이 "index0" 안에 substring 으로 매칭되는 노이즈 차단
      (c) co-occurrence — var + value 가 같은 line 에 있으면 +2 (분산보다 강함)
      (d) expression pattern — regex `var\\s*op\\s*value` 정확 매칭 시 verdict=yes 강한 신호
      - var 매칭 없이 op/value 만 hit → likely_no (이전엔 likely_yes 노이즈)

    Phase 16B — `var_aliases_per_cond`: condition 별 한·영 alias list. body 매칭 시
    var 와 함께 alias 도 시도하여 "두께" var + body "thickness" 같은 cross-lingual
    gap 해결. None 이면 기존 동작 (backward compat).
    """
    if not conditions:
        return ("unknown", "조건 추출 실패 — hypothesis 응답 불가", 0, 0)

    import re as _re

    body_text = body_text or ""
    body_lower = body_text.lower()
    body_lines = body_text.splitlines()
    body_signals = 0
    rule_signals = 0
    has_expression_match = False
    matched_var = ""
    matched_op = ""
    op_words = ("<=", ">=", "==", "!=", "<", ">", "equals", "compareTo")
    # Phase 16F — per-condition match tracking (AND semantic)
    per_cond_matched: list[bool] = []  # True 면 condition 가 body 에 매칭

    def _word_boundary_present(text: str, needle: str) -> bool:
        """needle 이 text 안에서 word boundary 로 등장하는지."""
        if not needle:
            return False
        # 영문/숫자 token 은 `\b` 사용. 한국어 + special char 는 그냥 substring.
        if _re.match(r"^[A-Za-z0-9_.]+$", needle):
            return bool(_re.search(rf"(?<!\w){_re.escape(needle)}(?!\w)", text))
        return needle in text

    for cond_idx, cond in enumerate(conditions):
        var = (cond.get("var") or "").strip()
        value = (cond.get("value") or "").strip()
        op = (cond.get("op") or "").strip()
        if not var or not value:
            per_cond_matched.append(False)
            continue

        # Phase 16B — var + alias list 통합 후보로 body 매칭 시도
        var_candidates: list[str] = [var]
        if var_aliases_per_cond and cond_idx < len(var_aliases_per_cond):
            for a in var_aliases_per_cond[cond_idx]:
                a_s = (a or "").strip()
                if a_s and a_s.lower() not in {v.lower() for v in var_candidates}:
                    var_candidates.append(a_s)

        # Phase 16F — per-condition match tracking
        cond_expression_hit = False
        cond_var_hit = False

        # (a) var token AND 매칭 — 어떤 candidate (var 본체 + alias) 라도 hit 하면 var match
        body_hit_var = False
        matched_var_candidate = ""
        matched_var_tokens: list[str] = []
        for cv in var_candidates:
            cv_tokens = [t.strip() for t in cv.split() if t.strip()]
            full_hit = cv.lower() in body_lower if cv else False
            all_tokens_hit = all(
                t.lower() in body_lower for t in cv_tokens
            ) if cv_tokens else False
            if full_hit or all_tokens_hit:
                body_hit_var = True
                matched_var_candidate = cv
                matched_var_tokens = cv_tokens
                break
        cond_var_hit = body_hit_var

        # 기본 (legacy) var_tokens — 다른 분기 (co-occurrence) 에서 사용
        var_tokens = matched_var_tokens or [
            t.strip() for t in var.split() if t.strip()
        ]
        if body_hit_var:
            body_signals += 1
            matched_var = matched_var_candidate or var

        # (b) value word-boundary 매칭
        body_hit_value = _word_boundary_present(body_text, value)
        if body_hit_value:
            body_signals += 1

        # (c) co-occurrence (var + value 같은 line) — matched candidate 사용
        if body_hit_var and body_hit_value:
            mv_lower = matched_var_candidate.lower()
            for line in body_lines:
                line_lower = line.lower()
                line_var = (
                    mv_lower in line_lower
                    or all(t.lower() in line_lower for t in var_tokens)
                )
                line_val = _word_boundary_present(line, value)
                if line_var and line_val:
                    body_signals += 2  # co-occurrence boost
                    break

        # (d) expression pattern — `var op value` (각 candidate 시도)
        if op and value:
            op_re = _re.escape(op)
            val_re = _re.escape(value)
            for cv in var_candidates:
                cv_tokens = [t.strip() for t in cv.split() if t.strip()]
                cv_re = _re.escape(cv) if (
                    not cv_tokens or len(cv_tokens) == 1
                ) else r"\s+".join(_re.escape(t) for t in cv_tokens)
                pat = rf"{cv_re}\s*{op_re}\s*{val_re}"
                try:
                    if _re.search(pat, body_text, _re.IGNORECASE):
                        has_expression_match = True
                        cond_expression_hit = True
                        body_signals += 3
                        matched_op = op
                        if not matched_var:
                            matched_var = cv
                        break
                except _re.error:
                    continue

        # Phase 16F — per-condition matched: expression hit OR (var hit + value hit)
        per_cond_matched.append(
            cond_expression_hit or (cond_var_hit and body_hit_value),
        )

        # op 단독 hit (정확 매칭은 d 가 처리, 여기는 약한 신호)
        if not has_expression_match and any(o in body_text for o in op_words):
            body_signals += 1
            if not matched_op:
                matched_op = op

        # business_rules 매칭 (변경 없음)
        for ev in evidence:
            stmt_lower = (ev.statement or "").lower()
            if any(t.lower() in stmt_lower for t in var_tokens if t):
                rule_signals += 1
                if value and value.lower() in stmt_lower:
                    rule_signals += 1

    # Phase 16F — multi-cond AND semantic: per-condition matched count
    matched_cond_count = sum(1 for m in per_cond_matched if m)
    total_cond_count = len(per_cond_matched)
    cond_match_suffix = ""
    is_multi_cond = total_cond_count > 1
    if is_multi_cond:
        if matched_cond_count == total_cond_count:
            cond_match_suffix = f" · 조건 {matched_cond_count}/{total_cond_count} 매칭 (모든 조건)"
        elif matched_cond_count > 0:
            cond_match_suffix = f" · 조건 {matched_cond_count}/{total_cond_count} 매칭 (partial)"
        else:
            cond_match_suffix = f" · 조건 0/{total_cond_count} 매칭"

    # Verdict 결정 (Phase 14D 강화 + Phase 16F multi-cond AND)
    if has_expression_match:
        # multi-cond 일 때 AND semantic: 모두 매칭 시만 yes 유지, partial 시 약화
        if is_multi_cond and matched_cond_count < total_cond_count:
            verdict: HypothesisVerdict = "likely_yes"
        else:
            verdict = "yes" if rule_signals >= 1 else "likely_yes"
        reasoning = (
            f"body 안에 정확한 expression `{matched_var} {matched_op} ...` 매칭 발견"
            + (f" + business_rule {rule_signals} 행 보강" if rule_signals else "")
            + cond_match_suffix
        )
    elif body_signals >= 5 and matched_var:  # var hit + co-occurrence boost (+2)
        verdict = "likely_yes"
        reasoning = (
            f"body 안에 변수/값 co-occurrence + 시그널 {body_signals} 강함"
        )
    elif body_signals >= 3 and rule_signals >= 1:
        verdict = "likely_yes"
        reasoning = (
            f"body 안에 변수/값/연산자 모두 발견 ({body_signals} 시그널) + "
            f"business_rule {rule_signals} 행 보강"
        )
    elif body_signals >= 2 and matched_var:
        verdict = "likely_yes"
        reasoning = (
            f"body 안에 변수+값/연산자 시그널 {body_signals} 발견"
        )
    elif body_signals >= 1 and not matched_var and rule_signals >= 2:
        # Phase 16A — var 매칭 없지만 rule_signals 강하면 likely_yes (rule 이 우선)
        verdict = "likely_yes"
        reasoning = (
            f"body 변수 매칭 약함 (한·영 alias 갭 가능) 이나 business_rule "
            f"{rule_signals} 행이 조건과 강하게 관련 → rule 기반 추정"
        )
    elif body_signals >= 1 and not matched_var:
        # var 매칭 없이 op/value 만 hit → false positive 위험. 약한 부정 신호.
        verdict = "likely_no"
        reasoning = (
            "body 에 변수 매칭 없음 — 연산자/값 매칭만으로는 조건 활성 판단 불가"
        )
    elif rule_signals >= 1 and body_signals == 0:
        verdict = "likely_yes"
        reasoning = (
            f"business_rule {rule_signals} 행이 조건과 관련 — body 직접 검증 안 됨"
        )
    elif body_signals == 0 and rule_signals == 0:
        verdict = "unknown"
        reasoning = (
            "body / business_rules 모두에서 조건 변수 / 값 시그널 못 찾음 — "
            "다른 method 일 가능성"
        )
    else:
        verdict = "likely_yes"
        reasoning = "조건과 관련된 시그널 일부 발견"

    if matched_var or matched_op:
        suffix = f" (matched var={matched_var!r}, op={matched_op!r})"
        reasoning = (reasoning + suffix)[:400]
    # Phase 16F (QA fix) — N/M suffix 를 모든 verdict 분기에 부착 (이전엔
    # has_expression_match 분기에만 surface 되던 dead code 해결).
    if is_multi_cond and cond_match_suffix not in reasoning:
        reasoning = (reasoning + cond_match_suffix)[:400]
    return (verdict, reasoning, body_signals, rule_signals)


__all__ = ["build_gate_hypothesis"]
