"""LLM-powered metadata suggestion service with tag normalization.

Architecture:
- Prompts are externalized to backend/application/agent/skills/prompts/auto_tag*.md
- 2-pass inference: Pass 1 (domain/process) → Pass 2 (tags scoped to that domain)
- Context signals: file path, parent directory, neighbor tags, neighbor domains, related docs
- Always-normalize: every LLM-suggested tag passes through tag_registry.find_similar
- Soft policy: new tags that pass normalization carry `tag_alternatives` for the UI to surface
- Confidence auto-correction based on normalization signals
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import litellm

from backend.core.config import settings
from backend.core.schemas import MetadataSuggestion, TagAlternative

logger = logging.getLogger(__name__)

TEMPLATES_FILE = Path(settings.wiki_dir) / ".ontong" / "metadata_templates.json"

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "application" / "agent" / "skills" / "prompts"
EXAMPLES_FILE = Path(__file__).resolve().parent / "auto_tag_examples.json"

# Will be set by main.py during startup
_meta_index = None
_tag_registry = None

# Normalization thresholds (calibrated for OpenAI text-embedding-3-small on short Korean tags)
AUTO_REPLACE_DIST = 0.35     # below this → silently replace
LLM_CONFIRM_DIST = 0.55      # 0.35 ~ 0.55 → ask LLM to confirm
SOFT_ALTERNATIVE_DIST = 0.65  # below this → surface as alternative for the user

_prompt_cache: dict[str, str] = {}
_examples_cache: dict | None = None


def init(meta_index=None, tag_registry=None) -> None:
    """Wire dependencies from main.py."""
    global _meta_index, _tag_registry
    _meta_index = meta_index
    _tag_registry = tag_registry


# ── Prompt loading ───────────────────────────────────────────────────

def _load_prompt(name: str) -> str:
    if name in _prompt_cache:
        return _prompt_cache[name]
    path = PROMPTS_DIR / f"{name}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to load prompt {name}: {e}")
        text = ""
    _prompt_cache[name] = text
    return text


def _load_examples() -> dict:
    global _examples_cache
    if _examples_cache is not None:
        return _examples_cache
    try:
        _examples_cache = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load auto-tag examples: {e}")
        _examples_cache = {"examples": []}
    return _examples_cache


def _format_few_shot(domain: str | None = None) -> str:
    data = _load_examples()
    examples = data.get("examples", [])
    if domain:
        scoped = [e for e in examples if e.get("domain") == domain]
        if scoped:
            examples = scoped
    out = []
    for e in examples:
        out.append(
            f"### {e.get('domain', '')} 예시\n"
            f"- 경로: `{e.get('path', '')}`\n"
            f"- 본문 발췌: {e.get('input_excerpt', '')}\n"
            f"- 정답:\n```json\n{json.dumps(e.get('output', {}), ensure_ascii=False, indent=2)}\n```"
        )
    return "\n\n".join(out) if out else "(예시 없음)"


def _get_existing_tags(limit: int = 100) -> list[str]:
    """Get existing tag names from index, sorted by usage count desc."""
    if not _meta_index:
        return []
    try:
        d = _meta_index._load()
        tags: dict[str, int] = d.get("tags", {})
        sorted_tags = sorted(tags.items(), key=lambda x: -x[1])
        return [t for t, _ in sorted_tags[:limit]]
    except Exception:
        return []


def _format_domains_info() -> str:
    try:
        if TEMPLATES_FILE.exists():
            data = json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
            dp = data.get("domain_processes", {})
            return "\n".join(f'  - "{d}": processes [{", ".join(p)}]' for d, p in dp.items())
    except Exception:
        pass
    return '  - "SCM", "ERP", "MES", "인프라", "기획", "재무", "인사"'


def _format_tag_list(tags: list[str]) -> str:
    return ", ".join(tags) if tags else "(없음)"


def _format_neighbor_tags(items: list[tuple[str, int]]) -> str:
    if not items:
        return "(같은 폴더에 다른 문서가 없습니다)"
    return ", ".join(f"{t}({c})" for t, c in items)


def _format_neighbor_summary(summary: dict) -> str:
    domains = summary.get("domains", {})
    processes = summary.get("processes", {})
    if not domains and not processes:
        return "(같은 폴더에 다른 문서가 없습니다)"
    dom_str = ", ".join(f"{d}({c})" for d, c in sorted(domains.items(), key=lambda x: -x[1]))
    proc_str = ", ".join(f"{p}({c})" for p, c in sorted(processes.items(), key=lambda x: -x[1]))
    return f"도메인 분포: {dom_str or '없음'}\n프로세스 분포: {proc_str or '없음'}"


def _split_path(path: str | None) -> tuple[str, str, str]:
    """Returns (filename, parent_dir, full_path) — empty strings if path is None."""
    if not path:
        return ("", "", "")
    p = path.strip("/")
    if "/" in p:
        parent, name = p.rsplit("/", 1)
    else:
        parent, name = "", p
    return (name, parent, path)


# ── Always-normalize: pass every tag through tag_registry ───────────

async def _normalize_one_tag(tag: str) -> tuple[str, list[TagAlternative], bool]:
    """Normalize a single tag.

    Returns (final_tag, alternatives, was_replaced).
    - was_replaced=True means the tag was silently replaced (auto or LLM-confirmed)
    - alternatives is the soft list shown to the user when the tag is kept as new
    """
    if not _tag_registry or not _tag_registry.is_connected:
        return (tag, [], False)

    similar = _tag_registry.find_similar(tag, top_k=5)
    candidates = [s for s in similar if s["tag"] != tag]
    if not candidates:
        return (tag, [], False)

    best = candidates[0]

    # Layer A: auto-replace if very close
    if best["distance"] < AUTO_REPLACE_DIST:
        logger.info(f"Tag auto-normalized: '{tag}' → '{best['tag']}' (dist={best['distance']:.3f})")
        return (best["tag"], [], True)

    # Layer B: LLM confirm for moderate similarity
    if best["distance"] < LLM_CONFIRM_DIST:
        candidate_names = [c["tag"] for c in candidates[:3]]
        try:
            response = await litellm.acompletion(
                model=settings.litellm_model,
                messages=[
                    {"role": "system", "content": "You are a tag deduplication assistant. Answer with ONLY the matching tag name, or 'NONE' if no match."},
                    {"role": "user", "content": f'Is the tag "{tag}" the same concept as any of these existing tags: {candidate_names}? If yes, respond with the matching tag name. If no, respond with NONE.'},
                ],
                temperature=0.0,
                max_tokens=50,
            )
            answer = response.choices[0].message.content.strip().strip('"').strip("'")
            if answer != "NONE" and answer in candidate_names:
                logger.info(f"Tag LLM-normalized: '{tag}' → '{answer}' (dist={best['distance']:.3f})")
                return (answer, [], True)
        except Exception as e:
            logger.warning(f"Tag normalization LLM call failed: {e}")

    # Layer C: keep new tag, surface soft alternatives if any are close enough
    alts: list[TagAlternative] = []
    for c in candidates[:3]:
        if c["distance"] < SOFT_ALTERNATIVE_DIST:
            alts.append(TagAlternative(tag=c["tag"], distance=c["distance"], count=c.get("count", 0)))
    return (tag, alts, False)


async def _normalize_tags_full(
    raw_tags: list[str], existing_doc_tags: list[str]
) -> tuple[list[str], dict[str, list[TagAlternative]], dict[str, str]]:
    """Pass every raw tag through normalization. Returns (final_tags, alternatives_map, replaced_map)."""
    if not _tag_registry or not _tag_registry.is_connected:
        return (raw_tags, {}, {})

    final: list[str] = []
    alternatives_map: dict[str, list[TagAlternative]] = {}
    replaced_map: dict[str, str] = {}
    seen: set[str] = set(existing_doc_tags)

    for tag in raw_tags:
        if not tag or tag in seen:
            continue
        # Always normalize — don't trust index presence, since the index can
        # already contain a degraded duplicate (e.g., 캐싱 when 캐시 also exists).
        # `_normalize_one_tag` returns (tag, [], False) when the tag itself is
        # the best match, so this is a near-zero overhead path for canonical tags.
        normalized, alts, was_replaced = await _normalize_one_tag(tag)
        if was_replaced:
            replaced_map[tag] = normalized
        if normalized in seen:
            continue
        final.append(normalized)
        seen.add(normalized)
        if not was_replaced:
            # New tag — register it for future matching
            try:
                _tag_registry.register_tag(normalized)
            except Exception:
                pass
            if alts:
                alternatives_map[normalized] = alts

    return (final, alternatives_map, replaced_map)


# ── 2-pass inference ─────────────────────────────────────────────────

async def _pass1_domain(content: str, path: str | None) -> dict:
    """Pass 1: determine domain + process from content + path + neighbor signals."""
    filename, parent, full = _split_path(path)
    neighbor_summary = (
        _meta_index.get_neighbor_domain_summary(parent, exclude_path=full)
        if _meta_index and parent
        else {"domains": {}, "processes": {}}
    )

    template = _load_prompt("auto_tag_pass1")
    system_prompt = (
        template
        .replace("{domains_info}", _format_domains_info())
        .replace("{path}", full or "(unknown)")
        .replace("{filename}", filename or "(unknown)")
        .replace("{parent_dir}", parent or "(root)")
        .replace("{neighbor_summary}", _format_neighbor_summary(neighbor_summary))
    )

    user_prompt = f"Document content:\n\n{content[:2500]}"

    try:
        response = await litellm.acompletion(
            model=settings.litellm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Auto-tag pass1 failed: {e}")
        return {"domain": "", "process": "", "confidence": 0.0, "reasoning": str(e)}


async def _pass2_tags(content: str, path: str | None, domain: str, process: str) -> dict:
    """Pass 2: select tags scoped to the domain decided in pass 1."""
    filename, parent, full = _split_path(path)

    domain_tags = (
        _meta_index.get_tags_for_domain(domain, top_k=50)
        if _meta_index and domain
        else []
    )
    neighbor_tags = (
        _meta_index.get_neighbor_tags(parent, exclude_path=full, top_k=20)
        if _meta_index and parent
        else []
    )
    existing_tags = _get_existing_tags(150)

    template = _load_prompt("auto_tag_pass2")
    system_prompt = (
        template
        .replace("{domain}", domain or "(unknown)")
        .replace("{process}", process or "(unknown)")
        .replace("{path}", full or "(unknown)")
        .replace("{domain_tags}", _format_neighbor_tags(domain_tags))
        .replace("{neighbor_tags}", _format_neighbor_tags(neighbor_tags))
        .replace("{existing_tags}", _format_tag_list(existing_tags))
        .replace("{few_shot_examples}", _format_few_shot(domain))
    )

    user_prompt = f"Document content:\n\n{content[:3000]}"

    try:
        response = await litellm.acompletion(
            model=settings.litellm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Auto-tag pass2 failed: {e}")
        return {"tags": [], "error_codes": [], "confidence": 0.0, "reasoning": str(e)}


# ── Public API ───────────────────────────────────────────────────────

async def suggest_metadata(
    content: str,
    existing_tags: list[str] | None = None,
    path: str | None = None,
    related: list[str] | None = None,
) -> MetadataSuggestion:
    """Use LLM to suggest metadata for a document.

    Two-pass inference:
      Pass 1: domain/process from content + path + neighbor domain distribution
      Pass 2: tags scoped to domain, with domain-frequent + neighbor tag injection
    All suggested tags are then normalized through tag_registry.

    Args:
        content: document body
        existing_tags: tags already on the document (excluded from suggestions)
        path: file path (e.g., "wiki/인프라/캐시-장애.md") — strong signal
        related: list of related document paths (lineage signal)
    """
    existing = existing_tags or []

    try:
        # Pass 1: domain/process
        pass1 = await _pass1_domain(content, path)
        domain = pass1.get("domain", "") or ""
        process = pass1.get("process", "") or ""
        pass1_conf = float(pass1.get("confidence", 0.5) or 0.5)

        # Pass 2: tags scoped to domain
        pass2 = await _pass2_tags(content, path, domain, process)
        raw_tags: list[str] = [t for t in pass2.get("tags", []) if t and t not in existing]
        error_codes = pass2.get("error_codes", []) or []
        pass2_conf = float(pass2.get("confidence", 0.5) or 0.5)

        # Always-normalize all proposed tags
        final_tags, alternatives, replaced = await _normalize_tags_full(raw_tags, existing)

        # Confidence: average of two passes, then auto-correct
        confidence = (pass1_conf + pass2_conf) / 2

        # Signal: alternatives present → many new tags couldn't be confidently mapped
        if alternatives:
            confidence -= 0.05 * min(len(alternatives), 3)
        # Signal: most tags came from existing vocabulary → high signal
        existing_set = set(_get_existing_tags(500))
        if final_tags:
            reused_ratio = sum(1 for t in final_tags if t in existing_set) / len(final_tags)
            if reused_ratio >= 0.7:
                confidence += 0.05
        # Signal: domain matches neighbor majority → locality agreement
        if domain and path and _meta_index:
            _, parent, _ = _split_path(path)
            summary = _meta_index.get_neighbor_domain_summary(parent, exclude_path=path)
            neighbor_doms = summary.get("domains", {})
            if neighbor_doms and max(neighbor_doms, key=neighbor_doms.get) == domain:
                confidence += 0.05

        confidence = max(0.0, min(1.0, confidence))

        reasoning_parts = []
        if pass1.get("reasoning"):
            reasoning_parts.append(f"[도메인] {pass1['reasoning']}")
        if pass2.get("reasoning"):
            reasoning_parts.append(f"[태그] {pass2['reasoning']}")
        if replaced:
            replaced_str = ", ".join(f"{k}→{v}" for k, v in replaced.items())
            reasoning_parts.append(f"[정규화] {replaced_str}")

        return MetadataSuggestion(
            domain=domain,
            process=process,
            error_codes=error_codes,
            tags=final_tags,
            confidence=confidence,
            reasoning=" / ".join(reasoning_parts),
            tag_alternatives=alternatives,
            tag_replaced=replaced,
        )

    except Exception as e:
        logger.error(f"Metadata suggestion failed: {e}")
        return MetadataSuggestion(
            confidence=0.0,
            reasoning=f"추천 실패: {e}",
        )
