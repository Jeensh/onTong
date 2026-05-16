"""W45 — production domain layer loader.

Sister to W42's `production_jpa_loader` but for the Domain layer. Reads
`business_terms` / `actions` / `anchor_bindings` from a production session
and exposes them as frozen Pydantic views suitable for cross-layer queries.

The Domain layer is owned by Section 2 (modeling); Section 4 (sim_v2) accesses
it strictly read-only via these loaders.

Public API:
    - BusinessTermView / ActionView / AnchorBindingView   — Pydantic frozen
    - load_business_terms(session, repo_id)
    - load_actions(session, repo_id)                       — parses code_method_fqn out of description
    - load_anchor_bindings(session, repo_id)
    - extract_method_fqn_from_description(text)            — pure helper
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session


# ─────────────────────────────────────────────────────────────────────────────
# Views — Pydantic frozen
# ─────────────────────────────────────────────────────────────────────────────


class BusinessTermView(BaseModel):
    model_config = ConfigDict(frozen=True)

    fqn:         str
    label:       str
    domain:      str = ""
    kind:        str = ""
    description: str = ""
    value_type:  str | None = None
    repo_id:     str = ""


class ActionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    fqn:                str
    label:              str
    kind:               str = ""
    declared_on_term:   str = ""
    description:        str = ""
    code_method_fqn:    str | None = None  # parsed out of description if present
    sub_actions:        tuple[str, ...] = Field(default_factory=tuple)
    repo_id:            str = ""


class AnchorBindingView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id:                str
    anchor_locator:    str
    code_method_fqn:   str = ""
    target_action_fqn: str = ""
    target_slot:       str | None = None
    confidence:        float = 1.0
    source:            str = ""
    repo_id:           str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Description → code_method_fqn extraction
# ─────────────────────────────────────────────────────────────────────────────


# Section 2 의 authoring 결과는 action.description 에
#   "자동 추천 — <code_method_fqn>"  형태로 stash 된다.
# Section 4 가 description 만으로 code↔action link 를 추론할 수 있도록 정규식 추출.
_DESC_FQN_RE = re.compile(r"자동\s*추천\s*[—–\-]\s*(?P<fqn>[\w\.$]+\([^)]*\))")


def extract_method_fqn_from_description(description: str) -> str | None:
    """Return the code method FQN embedded in an action.description, or None.

    Accepts both 'em-dash —', 'en-dash –', and hyphen '-' as separator.
    """
    if not description:
        return None
    m = _DESC_FQN_RE.search(description)
    return m.group("fqn") if m else None


# ─────────────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────────────


def load_business_terms(session: Session, repo_id: str) -> list[BusinessTermView]:
    rows = session.execute(
        text(
            "SELECT fqn, label, kind, domain, description, value_type "
            "FROM business_terms WHERE repo_id = :rid"
        ),
        {"rid": repo_id},
    ).fetchall()
    return [
        BusinessTermView(
            fqn=row[0],
            label=row[1] or "",
            kind=row[2] or "",
            domain=row[3] or "",
            description=row[4] or "",
            value_type=row[5],
            repo_id=repo_id,
        )
        for row in rows
    ]


def load_actions(session: Session, repo_id: str) -> list[ActionView]:
    rows = session.execute(
        text(
            "SELECT fqn, label, kind, declared_on_term, description, sub_actions_json "
            "FROM actions WHERE repo_id = :rid"
        ),
        {"rid": repo_id},
    ).fetchall()
    result: list[ActionView] = []
    for row in rows:
        description = row[4] or ""
        sub_actions: tuple[str, ...] = ()
        if row[5]:
            try:
                parsed = json.loads(row[5])
                if isinstance(parsed, list):
                    sub_actions = tuple(s for s in parsed if isinstance(s, str))
            except json.JSONDecodeError:
                pass
        result.append(ActionView(
            fqn=row[0],
            label=row[1] or "",
            kind=row[2] or "",
            declared_on_term=row[3] or "",
            description=description,
            code_method_fqn=extract_method_fqn_from_description(description),
            sub_actions=sub_actions,
            repo_id=repo_id,
        ))
    return result


def load_anchor_bindings(session: Session, repo_id: str) -> list[AnchorBindingView]:
    rows = session.execute(
        text(
            "SELECT id, anchor_locator, code_method_fqn, target_action_fqn, "
            "       target_slot, confidence, source "
            "FROM anchor_bindings WHERE repo_id = :rid"
        ),
        {"rid": repo_id},
    ).fetchall()
    return [
        AnchorBindingView(
            id=row[0],
            anchor_locator=row[1] or "",
            code_method_fqn=row[2] or "",
            target_action_fqn=row[3] or "",
            target_slot=row[4],
            confidence=float(row[5] or 1.0),
            source=row[6] or "",
            repo_id=repo_id,
        )
        for row in rows
    ]


__all__ = [
    "ActionView",
    "AnchorBindingView",
    "BusinessTermView",
    "extract_method_fqn_from_description",
    "load_actions",
    "load_anchor_bindings",
    "load_business_terms",
]
