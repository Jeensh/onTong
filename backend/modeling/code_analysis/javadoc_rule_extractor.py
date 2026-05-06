"""OD-11-E1-d (A3) — Javadoc → BusinessRule 추출기.

한국어 Javadoc 룰 문장을 `BusinessRule` Pydantic DTO + `VALIDATES` 엣지로 변환.
CONFLICTS_WITH gap 감지 (`RuleASTDiffer`) 의 **코드 쪽 rule 입력**.

스코프
- `/** ... */` Javadoc 만 처리, 일반 `/* */` block_comment 는 skip.
- 타겟 = class / interface / enum / method / constructor (field 는 v1 skip).
- Rule FQN = `{target_fqn}#rule{N}` (1-indexed, deterministic per file).
- Severity = HARD if 금지 keyword (불가/금지/허용되지/던진다/Exception/차단/초과할 수 없) else SOFT.

스펙 외
- term resolution (`terms_ref`) : 추출 시점에는 빈 list. C3 `TermResolver` 가
  별도 단계에서 채우거나, 사람 검토 시 보강.
- 매칭 confidence : 추출기는 발견만 하고 점수는 매기지 않음. 사람 승인 큐에서 처리.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser

from backend.modeling.code_analysis.parser_protocol import (
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity

_JAVA_LANGUAGE = Language(tsjava.language())


# ---------------------------------------------------------------------------
# Heuristic patterns
# ---------------------------------------------------------------------------
# 룰성 문장 판정 — 아래 중 하나라도 매칭되면 후보로 채택.
_RULE_KEYWORD_RE = re.compile(
    r"이상|이하|초과|미만|동일|같음|"
    r"할\s*수\s*없|불가|금지|허용되지\s*않|던진다|"
    r"해야\s*한다|되어야\s*한다|이어야\s*한다|여야\s*한다"
)
_RULE_INEQUALITY_RE = re.compile(r"≤|≥|<=|>=|==|!=")

# HARD severity 트리거 — 위반 시 차단.
_HARD_KEYWORD_RE = re.compile(
    r"불가|금지|허용되지\s*않|던진다|차단|거부|초과할\s*수\s*없|"
    r"IllegalArgumentException|Exception"
)

# Bullet 마커 — 라인이 이걸로 시작하면 해당 라인 전체를 하나의 rule 후보.
_BULLET_RE = re.compile(r"^\s*[-*]\s+|^\s*\d+\.\s+")

# 문장 분리 — Korean : "다." / "요." / "니." 뒤 공백 또는 line break.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=다)\.\s+|(?<=요)\.\s+|(?<=니)\.\s+")

# Javadoc 라인 정리 — leading `*`, `/**`, `*/`, 선행/후행 공백 제거.
_JAVADOC_DECOR_RE = re.compile(r"^\s*\*+/?|/?\*+\s*$")

# 타겟이 될 수 있는 declaration node type.
_TARGET_DECL_TYPES = frozenset(
    {
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "method_declaration",
        "constructor_declaration",
    }
)

_CLASS_LIKE_TYPES = frozenset(
    {"class_declaration", "interface_declaration", "enum_declaration"}
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _JavadocBlock:
    """Javadoc 코멘트 1 개와 그 다음 declaration."""
    raw_text: str
    decl_node: Node


class JavadocRuleExtractor:
    """`/** ... */` Javadoc → `BusinessRule` + `VALIDATES` 엣지 추출기."""

    def __init__(self, *, now: datetime | None = None) -> None:
        # 테스트 결정성 — 외부에서 시간을 주입할 수 있게 하되,
        # 기본은 호출 시점의 UTC.
        self._now = now
        self._parser = Parser(_JAVA_LANGUAGE)

    def extract(
        self,
        file_path: str,
        content: str,
        parse_result: ParseResult,
    ) -> tuple[list[BusinessRule], list[CodeRelation]]:
        tree = self._parser.parse(content.encode())
        blocks = list(self._iter_javadoc_blocks(tree.root_node))
        if not blocks:
            return [], []

        # FQN 색인 — (line_start, kind 카테고리) → entity FQN
        # 같은 라인에 여러 entity 가 있을 수 있으나, decl 매칭은
        # `(line_start, kind)` 조합으로 충분히 유일.
        index = self._build_target_index(parse_result)

        rules: list[BusinessRule] = []
        edges: list[CodeRelation] = []

        # rule_counter[target_fqn] → 다음 rule 번호 (1-indexed).
        rule_counter: dict[str, int] = {}
        ts = self._now or datetime.now(timezone.utc)

        for block in blocks:
            target_fqn = self._resolve_target_fqn(block.decl_node, index)
            if target_fqn is None:
                continue

            sentences = _split_rule_candidates(block.raw_text)
            if not sentences:
                continue

            for sentence in sentences:
                rule_counter[target_fqn] = rule_counter.get(target_fqn, 0) + 1
                idx = rule_counter[target_fqn]
                rule_fqn = f"{target_fqn}#rule{idx}"

                rule = BusinessRule(
                    qualified_name=rule_fqn,
                    statement=sentence,
                    terms_ref=[],
                    severity=_classify_severity(sentence),
                    source=f"javadoc:{target_fqn}",
                    confirmed=False,
                    created_at=ts,
                )
                rules.append(rule)
                edges.append(
                    CodeRelation(
                        kind=RelationKinds.VALIDATES,
                        source=rule_fqn,
                        target=target_fqn,
                        file_path=file_path,
                        line=block.decl_node.start_point[0] + 1,
                    )
                )

        return rules, edges

    # -- internal -----------------------------------------------------------

    def _iter_javadoc_blocks(self, root: Node):
        """Javadoc(`/** ... */`) 직후의 declaration 만 yield."""
        for node in _walk(root):
            if node.type != "block_comment":
                continue
            text = node.text.decode("utf-8", errors="replace")
            if not text.startswith("/**"):
                continue
            decl = _next_declaration_sibling(node)
            if decl is None:
                continue
            yield _JavadocBlock(raw_text=text, decl_node=decl)

    def _build_target_index(self, pr: ParseResult) -> dict[tuple[int, str], str]:
        """(line_start, kind) → qualified_name 색인."""
        index: dict[tuple[int, str], str] = {}
        for e in pr.entities:
            index.setdefault((e.line_start, e.kind), e.qualified_name)
        return index

    def _resolve_target_fqn(
        self,
        decl: Node,
        index: dict[tuple[int, str], str],
    ) -> str | None:
        line = decl.start_point[0] + 1
        type_to_kinds: dict[str, tuple[str, ...]] = {
            "class_declaration": (EntityKinds.CLASS,),
            "interface_declaration": (EntityKinds.INTERFACE,),
            "enum_declaration": (EntityKinds.ENUM,),
            "method_declaration": (EntityKinds.METHOD,),
            "constructor_declaration": (EntityKinds.CONSTRUCTOR,),
        }
        for kind in type_to_kinds.get(decl.type, ()):
            fqn = index.get((line, kind))
            if fqn is not None:
                return fqn
        return None


def extract_rules_from_file(
    file_path: str,
    content: str,
    parse_result: ParseResult,
) -> tuple[list[BusinessRule], list[CodeRelation]]:
    """Module-level convenience — 신규 instance 생성 후 `extract` 호출."""
    return JavadocRuleExtractor().extract(file_path, content, parse_result)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _walk(node: Node):
    """Iterative DFS — JavaParser._walk 와 동일 패턴."""
    cursor = node.walk()
    visited = False
    while True:
        if not visited:
            yield cursor.node
            if cursor.goto_first_child():
                continue
        if cursor.goto_next_sibling():
            visited = False
            continue
        if not cursor.goto_parent():
            break
        visited = True


def _next_declaration_sibling(comment: Node) -> Node | None:
    """block_comment 의 다음 sibling 이 target declaration 인지 확인."""
    sib = comment.next_sibling
    while sib is not None:
        if sib.type in _TARGET_DECL_TYPES:
            return sib
        # `;` 이나 다른 코멘트가 끼어있어도 다음으로 진행.
        if sib.type in ("block_comment", "line_comment"):
            sib = sib.next_sibling
            continue
        # 그 외 (modifier 등) 가 끼면 — Javadoc 이 그 declaration 에 붙은 게 아님.
        # 보수적으로 None 반환.
        return None
    return None


def _strip_javadoc_decoration(raw: str) -> str:
    """`/** ... */` 안쪽 텍스트만 추출 (leading `*` 정리)."""
    body = raw.strip()
    if body.startswith("/**"):
        body = body[3:]
    if body.endswith("*/"):
        body = body[:-2]
    cleaned_lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        # leading `*` 제거 (한 칸 이상)
        if stripped.startswith("*"):
            stripped = stripped[1:].lstrip()
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def _split_rule_candidates(raw_javadoc: str) -> list[str]:
    """Javadoc 본문 → 룰 후보 문장 리스트.

    1. Javadoc 장식 제거.
    2. 라인 단위 분할 → bullet 라인은 단일 후보, 일반 라인은 `다.` `요.` 단위로 추가 분할.
    3. 룰 휴리스틱(_is_rule_like) 통과한 문장만 수집.
    """
    body = _strip_javadoc_decoration(raw_javadoc)
    candidates: list[str] = []

    for line in body.splitlines():
        line = line.rstrip()
        if not line:
            continue
        # bullet 면 마커 제거 후 한 후보
        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            text = line[bullet_match.end():].strip()
            for piece in _SENTENCE_SPLIT_RE.split(text):
                candidates.append(piece.strip())
        else:
            for piece in _SENTENCE_SPLIT_RE.split(line.strip()):
                candidates.append(piece.strip())

    rules: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        clean = _normalize_sentence(c)
        if not clean or clean in seen:
            continue
        if not _is_rule_like(clean):
            continue
        seen.add(clean)
        rules.append(clean)
    return rules


def _normalize_sentence(text: str) -> str:
    """문장 끝 마침표 보존, 다중 공백 압축."""
    s = re.sub(r"\s+", " ", text).strip()
    # 너무 짧은 단편 제거 (예: ".", "이상")
    if len(s) < 4:
        return ""
    return s


def _is_rule_like(sentence: str) -> bool:
    if _RULE_KEYWORD_RE.search(sentence):
        return True
    # 부등식 단독은 식별자(영문/한글) 가 같이 있어야 룰로 인정.
    if _RULE_INEQUALITY_RE.search(sentence) and re.search(r"[A-Za-z가-힣]", sentence):
        return True
    return False


def _classify_severity(sentence: str) -> RuleSeverity:
    if _HARD_KEYWORD_RE.search(sentence):
        return RuleSeverity.HARD
    return RuleSeverity.SOFT
