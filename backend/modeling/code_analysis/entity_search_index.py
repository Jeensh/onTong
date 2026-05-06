"""Per-repo in-memory entity search index — 5000+ class scale.

Goals:
  - O(1) lookup by fqn
  - Sub-50ms substring search across ~100K entities
  - Ranked: exact > startswith > contains, with kind preference
  - Faceted filters: kind, parent_class, has_term_binding, has_rule
  - Pagination (limit/offset/total)

Design:
  - Cache a flat list[CodeEntity] per repo on register (skip nested iteration)
  - Lowercase indexes (name_lower, fqn_lower) for fast `in`
  - Optional binding/rule overlay: caller passes `term_bindings_by_code_fqn` +
    `rule_count_by_method_fqn` so each result row carries badge counts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from backend.modeling.code_analysis.parser_protocol import CodeEntity


@dataclass
class EntityHit:
    qualified_name: str
    name: str
    kind: str
    parent: str | None
    file_path: str
    line_start: int
    score: int                          # higher = more relevant
    mapped_term_count: int = 0          # confirmed ConceptBindings on this fqn
    governing_rule_count: int = 0       # rules whose method_fqn = this fqn


@dataclass
class SearchResult:
    items: list[EntityHit]
    total: int                          # total matches before limit/offset
    truncated: bool                     # True if total > limit + offset


@dataclass
class EntitySearchIndex:
    """Lightweight per-repo index — built once at register, queried by API."""

    entities: list[CodeEntity] = field(default_factory=list)
    fqn_lower: list[str] = field(default_factory=list)
    name_lower: list[str] = field(default_factory=list)
    by_fqn: dict[str, CodeEntity] = field(default_factory=dict)
    by_kind: dict[str, list[int]] = field(default_factory=dict)
    children_by_parent: dict[str, list[int]] = field(default_factory=dict)

    @classmethod
    def build(cls, entities: Iterable[CodeEntity]) -> "EntitySearchIndex":
        idx = cls()
        for e in entities:
            if e.qualified_name in idx.by_fqn:
                continue
            i = len(idx.entities)
            idx.entities.append(e)
            idx.fqn_lower.append(e.qualified_name.lower())
            idx.name_lower.append((e.name or "").lower())
            idx.by_fqn[e.qualified_name] = e
            idx.by_kind.setdefault(e.kind, []).append(i)
            if e.parent:
                idx.children_by_parent.setdefault(e.parent, []).append(i)
        return idx

    # ---- query ----
    def search(
        self,
        q: str,
        *,
        kinds: Sequence[str] | None = None,
        parent_fqn: str | None = None,
        limit: int = 30,
        offset: int = 0,
        binding_count_by_fqn: dict[str, int] | None = None,
        rule_count_by_method: dict[str, int] | None = None,
    ) -> SearchResult:
        q_lower = q.strip().lower()

        # 1) Candidate index pool (intersection of filters)
        if kinds:
            candidates: list[int] = []
            for k in kinds:
                candidates.extend(self.by_kind.get(k, ()))
            candidates.sort()
        elif parent_fqn:
            candidates = list(self.children_by_parent.get(parent_fqn, ()))
        else:
            candidates = list(range(len(self.entities)))

        if parent_fqn and kinds:
            child_set = set(self.children_by_parent.get(parent_fqn, ()))
            candidates = [i for i in candidates if i in child_set]

        # 2) Score each candidate
        hits: list[tuple[int, int]] = []  # (score, index)
        for i in candidates:
            if q_lower:
                name = self.name_lower[i]
                fqn = self.fqn_lower[i]
                if q_lower == name:
                    score = 100
                elif name.startswith(q_lower):
                    score = 80
                elif q_lower in name:
                    score = 60
                elif q_lower in fqn:
                    score = 30
                else:
                    continue
            else:
                score = 10
            # tiny boost for class/method/term (most useful nav targets)
            kind = self.entities[i].kind
            if kind == "class":
                score += 5
            elif kind == "method":
                score += 3
            hits.append((score, i))

        hits.sort(key=lambda t: (-t[0], self.entities[t[1]].qualified_name))
        total = len(hits)
        page = hits[offset : offset + limit]
        truncated = (offset + limit) < total

        out: list[EntityHit] = []
        for score, i in page:
            e = self.entities[i]
            mtc = (binding_count_by_fqn or {}).get(e.qualified_name, 0)
            grc = (rule_count_by_method or {}).get(e.qualified_name, 0)
            out.append(EntityHit(
                qualified_name=e.qualified_name,
                name=e.name,
                kind=e.kind,
                parent=e.parent,
                file_path=e.file_path,
                line_start=e.line_start,
                score=score,
                mapped_term_count=mtc,
                governing_rule_count=grc,
            ))
        return SearchResult(items=out, total=total, truncated=truncated)

    # ---- stats ----
    def stats(self) -> dict[str, int]:
        out: dict[str, int] = {"total": len(self.entities)}
        for k, idxs in self.by_kind.items():
            out[k] = len(idxs)
        return out


__all__ = ("EntityHit", "EntitySearchIndex", "SearchResult")
