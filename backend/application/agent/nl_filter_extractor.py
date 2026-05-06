"""Natural-language → FilterSpec extractor.

Rule-based, deterministic, and cheap — runs on every user query before the
agent calls `wiki_search`, so the agent can pre-filter by folder, author,
doc_type, and mtime range without a round-trip to the LLM.

Design principles
-----------------
- Rule-based only (no LLM call). Fast + explainable.
- Conservative: return {} unless a pattern matches with high confidence.
- Works alongside the existing `filter_extractor.py` (domain/process) —
  this one produces a richer `FilterSpec` shape (folders/authors/types/mtime)
  that can be merged into `WikiSearchSkill.execute(filters=...)`.

The extracted FilterSpec is a narrow subset of the full spec documented in
`toClaude/wiki/specs/2026-04-17-metadata-search-design.md` §4.1 — it does NOT
produce `tags`, `path`, `statuses`, `acl`, or Boolean DSL fields. Those
require either UI selection or LLM tool-calling.
"""

from __future__ import annotations

import calendar
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger(__name__)


# ── Folder vocab ───────────────────────────────────────────────

# Seed list of top-level folder names we expect in the wiki root.
# Also catches well-known English abbreviations even when the actual folder
# is Korean (users say "ERP 폴더" but the folder may be `ERP/`).
_FOLDER_ALIASES: dict[str, list[str]] = {
    "ERP": ["ERP", "erp"],
    "MES": ["MES", "mes"],
    "SCM": ["SCM", "scm"],
    "인프라": ["인프라", "IT", "it"],
    "기획": ["기획"],
    "재무": ["재무", "회계"],
    "인사": ["인사", "HR", "hr"],
    "공정": ["공정"],
    "설비": ["설비"],
    "이슈": ["이슈", "인시던트", "incident"],
    "제품": ["제품"],
    "표준": ["표준"],
}


def _scan_top_folders() -> set[str]:
    """Scan the wiki root for top-level dirs that exist today."""
    try:
        root = Path(settings.wiki_dir)
        if not root.exists():
            return set()
        return {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_")}
    except Exception as exc:  # noqa: BLE001
        logger.debug("scan folders failed: %s", exc)
        return set()


def _extract_folders(query: str) -> list[str]:
    if not query:
        return []
    found: list[str] = []
    # 1) Alias-based: "ERP 폴더", "인프라"
    for canonical, aliases in _FOLDER_ALIASES.items():
        for a in aliases:
            # Word-ish boundary — Korean folders don't have \b, so require surrounding non-letter
            pattern = rf"(?:(?<=^)|(?<=[\s/,.])){re.escape(a)}(?:(?=$)|(?=[\s/,.폴더에서]))"
            if re.search(pattern, query):
                if canonical not in found:
                    found.append(canonical)
                break
    # 2) Filesystem-scan augmentation — catches new top folders we don't know about yet
    try:
        real = _scan_top_folders()
        for name in real:
            if name in found:
                continue
            # Require the literal folder name to appear as a standalone token
            if re.search(rf"(?:(?<=^)|(?<=[\s/,.])){re.escape(name)}(?:(?=$)|(?=[\s/,.폴더에서]))", query):
                found.append(name)
    except Exception:
        pass
    return found


# ── Authors ────────────────────────────────────────────────────

_AUTHOR_RE = re.compile(r"@([A-Za-z0-9가-힣_\-]+)")
_KOREAN_PARTICLES = ("가", "이", "은", "는", "을", "를", "의", "와", "과", "도", "만", "께서")


def _strip_particle(handle_body: str) -> str:
    """Strip a trailing Korean particle from a handle body.

    The author regex is greedy across hangul, so "@동해가 썼다" matches "@동해가".
    If the body ends with a known particle AND the prefix is at least 1 hangul,
    drop the particle.
    """
    for p in _KOREAN_PARTICLES:
        if handle_body.endswith(p) and len(handle_body) > len(p):
            prefix = handle_body[: -len(p)]
            if re.fullmatch(r"[가-힣]+", prefix):
                return prefix
    return handle_body


def _extract_authors(query: str) -> list[str]:
    if not query:
        return []
    seen: list[str] = []
    for m in _AUTHOR_RE.finditer(query):
        body = _strip_particle(m.group(1))
        handle = f"@{body}"
        if handle not in seen:
            seen.append(handle)
    return seen


# ── Types ──────────────────────────────────────────────────────

_TYPE_ALIASES: dict[str, list[str]] = {
    "sop": ["SOP", "sop", "표준 작업 절차", "표준작업절차"],
    "spec": ["spec", "사양서", "사양"],
    "plan": ["plan", "계획서", "계획"],
    "decision": ["decision", "결정", "의사결정"],
    "incident": ["incident", "인시던트", "사고", "장애"],
    "postmortem": ["postmortem", "포스트모템", "RCA", "rca"],
    "meeting": ["meeting", "미팅", "회의"],
    "skill": ["skill", "스킬"],
}


def _extract_types(query: str) -> list[str]:
    if not query:
        return []
    found: list[str] = []
    for canonical, aliases in _TYPE_ALIASES.items():
        for a in aliases:
            if a in query:
                if canonical not in found:
                    found.append(canonical)
                break
    return found


# ── mtime ─────────────────────────────────────────────────────

_DAYS_RE = re.compile(r"최근\s*(\d+)\s*일")
_YM_RE = re.compile(r"(\d{4})년\s*(\d{1,2})월")


def _iso(d: date) -> str:
    return d.isoformat()


def _first_day(y: int, m: int) -> date:
    return date(y, m, 1)


def _last_day(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _extract_mtime(query: str, *, today: date | None = None) -> dict:
    if not query:
        return {}
    today = today or date.today()
    out: dict = {}

    # "최근 N일"
    m = _DAYS_RE.search(query)
    if m:
        try:
            days = int(m.group(1))
            if 0 < days <= 3650:
                out["mtime_from"] = _iso(today - timedelta(days=days))
                return out
        except ValueError:
            pass

    # "지난 달" / "지난달"
    if re.search(r"지난\s*달", query):
        prev_month = today.month - 1
        prev_year = today.year
        if prev_month <= 0:
            prev_month = 12
            prev_year -= 1
        out["mtime_from"] = _iso(_first_day(prev_year, prev_month))
        out["mtime_to"] = _iso(_last_day(prev_year, prev_month))
        return out

    # "이번 달" / "이번달"
    if re.search(r"이번\s*달", query):
        out["mtime_from"] = _iso(_first_day(today.year, today.month))
        return out

    # "YYYY년 M월 이후/부터"
    m = _YM_RE.search(query)
    if m:
        try:
            y, mo = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12:
                out["mtime_from"] = _iso(_first_day(y, mo))
                # 이후/부터 → open-ended; 까지/이전 → close at month end
                if re.search(r"(까지|이전)", query):
                    out["mtime_to"] = _iso(_last_day(y, mo))
                return out
        except ValueError:
            pass

    return out


# ── End-to-end ────────────────────────────────────────────────

def extract_filter_spec(query: str, *, today: date | None = None) -> dict:
    """Extract a partial FilterSpec dict from a natural-language query.

    Returns {} when nothing confident matches — callers can merge with other
    filter sources (UI, LLM tool-call) safely.
    """
    if not query:
        return {}

    spec: dict = {}

    folders = _extract_folders(query)
    if folders:
        spec["folders"] = folders

    authors = _extract_authors(query)
    if authors:
        spec["authors"] = authors

    types = _extract_types(query)
    if types:
        spec["types"] = types

    mtime = _extract_mtime(query, today=today)
    if mtime:
        spec.update(mtime)

    if spec:
        logger.info("NL filter extracted: %s", spec)
    return spec
