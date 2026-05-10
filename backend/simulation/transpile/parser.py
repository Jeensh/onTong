"""tree-sitter (Java) 기반 메서드 추출 — transpile 단계의 입력 준비.

Section 2 의 backend/modeling/code_analysis/java_parser.py 와 동일한 tree-sitter 인스턴스를
재사용하기 위해 import 한다 (의존성/언어 객체 1회만 로드).

Public API
----------
- list_methods(java_path)              → list[JavaMethodInfo]  (시그니처만)
- extract_method(java_path, name)      → JavaMethodInfo (본문 포함) | None
- summarize_for_llm(info)              → str  (LLM prompt 에 넣을 요약 문자열)

JavaMethodInfo 는 일부러 lightweight dataclass — Pydantic 미사용 (LLM 입력에만 쓰임).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# tree_sitter 의존성은 이미 pyproject.toml 에 정의됨 (Section 2 modeling 와 공유).
try:
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Node, Parser

    _JAVA_LANGUAGE = Language(tsjava.language())
    _PARSER_AVAILABLE = True
except Exception as e:  # pragma: no cover — 환경 누락 시 graceful
    logger.warning(f"tree_sitter_java unavailable: {e}")
    _JAVA_LANGUAGE = None  # type: ignore[assignment]
    Node = object  # type: ignore[assignment]
    Parser = None  # type: ignore[assignment]
    _PARSER_AVAILABLE = False


@dataclass
class JavaMethodInfo:
    """자바 메서드 한 개 의 추출 정보 — LLM 변환 입력으로 사용."""

    file_path: str
    class_name: str
    method_name: str
    return_type: str
    parameters: list[tuple[str, str]] = field(default_factory=list)  # (type, name) 쌍
    modifiers: list[str] = field(default_factory=list)  # public / static / ...
    body_source: str = ""  # 메서드 본문 ({} 포함, 원본 들여쓰기 유지)
    signature_line: int = 0
    end_line: int = 0
    imports: list[str] = field(default_factory=list)  # 파일의 import 목록
    package: str = ""
    class_fields: list[tuple[str, str]] = field(default_factory=list)  # (type, name)
    javadoc: str = ""  # 메서드 직전 Javadoc 또는 //comment

    def signature(self) -> str:
        params = ", ".join(f"{t} {n}" for t, n in self.parameters)
        mods = " ".join(self.modifiers)
        return f"{mods} {self.return_type} {self.method_name}({params})".strip()


# ─── tree-sitter helpers ────────────────────────────────────────────


def _parser() -> Parser:
    if not _PARSER_AVAILABLE:
        raise RuntimeError("tree_sitter_java not available — check pyproject.toml dependencies")
    return Parser(_JAVA_LANGUAGE)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _find_first(node: Node, kind: str) -> Optional[Node]:
    for ch in node.children:
        if ch.type == kind:
            return ch
    return None


def _find_all(node: Node, kind: str) -> list[Node]:
    return [ch for ch in node.children if ch.type == kind]


def _walk(node: Node):
    yield node
    for ch in node.children:
        yield from _walk(ch)


# ─── parsing ───────────────────────────────────────────────────────


def _extract_class_decls(root: Node) -> list[Node]:
    """root 아래의 class_declaration 노드 목록."""
    out: list[Node] = []
    for n in _walk(root):
        if n.type == "class_declaration":
            out.append(n)
    return out


def _class_simple_name(class_node: Node, source: bytes) -> str:
    name_node = _find_first(class_node, "identifier")
    if name_node is not None:
        return _text(name_node, source)
    return "<anonymous>"


def _extract_imports(root: Node, source: bytes) -> list[str]:
    out: list[str] = []
    for ch in root.children:
        if ch.type == "import_declaration":
            txt = _text(ch, source).strip()
            # "import x.y.z;" → "x.y.z"
            txt = txt.removeprefix("import").rstrip(";").strip()
            if txt.startswith("static "):
                txt = txt.removeprefix("static").strip()
            out.append(txt)
    return out


def _extract_package(root: Node, source: bytes) -> str:
    for ch in root.children:
        if ch.type == "package_declaration":
            txt = _text(ch, source).strip()
            return txt.removeprefix("package").rstrip(";").strip()
    return ""


def _extract_class_fields(class_body: Node, source: bytes) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for ch in class_body.children:
        if ch.type == "field_declaration":
            type_node = _find_first(ch, "type_identifier") or _find_first(ch, "generic_type")
            type_str = _text(type_node, source) if type_node else "?"
            for var in _find_all(ch, "variable_declarator"):
                name_node = _find_first(var, "identifier")
                if name_node is not None:
                    out.append((type_str, _text(name_node, source)))
    return out


def _extract_method_params(method_node: Node, source: bytes) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    params_node = _find_first(method_node, "formal_parameters")
    if params_node is None:
        return out
    for ch in params_node.children:
        if ch.type == "formal_parameter":
            type_node = (
                _find_first(ch, "type_identifier")
                or _find_first(ch, "generic_type")
                or _find_first(ch, "integral_type")
                or _find_first(ch, "floating_point_type")
                or _find_first(ch, "array_type")
            )
            name_node = _find_first(ch, "identifier")
            type_str = _text(type_node, source) if type_node else "?"
            name_str = _text(name_node, source) if name_node else "?"
            out.append((type_str, name_str))
    return out


def _extract_modifiers(method_node: Node, source: bytes) -> list[str]:
    mods_node = _find_first(method_node, "modifiers")
    if mods_node is None:
        return []
    return [_text(ch, source) for ch in mods_node.children if ch.type != "marker_annotation"]


def _javadoc_before(method_node: Node, source: bytes, root: Node) -> str:
    """method_node 직전의 block_comment 또는 line_comment 가 Javadoc 역할."""
    parent = method_node.parent
    if parent is None:
        return ""
    siblings = list(parent.children)
    try:
        idx = siblings.index(method_node)
    except ValueError:
        return ""
    if idx == 0:
        return ""
    prev = siblings[idx - 1]
    if prev.type in ("block_comment", "line_comment"):
        return _text(prev, source).strip()
    return ""


def _build_info(
    method_node: Node,
    class_node: Node,
    root: Node,
    source: bytes,
    file_path: str,
) -> JavaMethodInfo:
    name_node = _find_first(method_node, "identifier")
    method_name = _text(name_node, source) if name_node else "<anonymous>"
    # return_type — 메서드 직속 자식 중 type 류
    return_type = "void"
    for ch in method_node.children:
        if ch.type in (
            "type_identifier",
            "void_type",
            "integral_type",
            "floating_point_type",
            "boolean_type",
            "generic_type",
            "array_type",
        ):
            return_type = _text(ch, source)
            break

    body_node = _find_first(method_node, "block")
    body_src = _text(body_node, source) if body_node else ""

    class_body = _find_first(class_node, "class_body")
    fields = _extract_class_fields(class_body, source) if class_body else []

    return JavaMethodInfo(
        file_path=file_path,
        class_name=_class_simple_name(class_node, source),
        method_name=method_name,
        return_type=return_type,
        parameters=_extract_method_params(method_node, source),
        modifiers=_extract_modifiers(method_node, source),
        body_source=body_src,
        signature_line=method_node.start_point[0] + 1,
        end_line=method_node.end_point[0] + 1,
        imports=_extract_imports(root, source),
        package=_extract_package(root, source),
        class_fields=fields,
        javadoc=_javadoc_before(method_node, source, root),
    )


def _parse_file(java_path: Path) -> tuple[Node, bytes]:
    source = java_path.read_bytes()
    tree = _parser().parse(source)
    return tree.root_node, source


# ─── public API ────────────────────────────────────────────────────


def list_methods(java_path: Path | str) -> list[JavaMethodInfo]:
    """파일의 모든 (top-level + nested) 메서드 시그니처 반환. body_source 는 비움."""
    p = Path(java_path)
    if not p.exists():
        raise FileNotFoundError(p)
    root, source = _parse_file(p)
    out: list[JavaMethodInfo] = []
    for class_node in _extract_class_decls(root):
        class_body = _find_first(class_node, "class_body")
        if class_body is None:
            continue
        for ch in class_body.children:
            if ch.type == "method_declaration":
                info = _build_info(ch, class_node, root, source, str(p))
                # 시그니처 목록에서는 body 비워서 가벼움 유지
                info.body_source = ""
                out.append(info)
    return out


def extract_method(
    java_path: Path | str,
    method_name: str,
    class_name: Optional[str] = None,
) -> Optional[JavaMethodInfo]:
    """이름으로 메서드 1개 추출 (본문 포함)."""
    p = Path(java_path)
    if not p.exists():
        raise FileNotFoundError(p)
    root, source = _parse_file(p)
    candidates: list[JavaMethodInfo] = []
    for class_node in _extract_class_decls(root):
        cname = _class_simple_name(class_node, source)
        if class_name and cname != class_name:
            continue
        class_body = _find_first(class_node, "class_body")
        if class_body is None:
            continue
        for ch in class_body.children:
            if ch.type == "method_declaration":
                name_node = _find_first(ch, "identifier")
                if name_node is None:
                    continue
                if _text(name_node, source) == method_name:
                    candidates.append(_build_info(ch, class_node, root, source, str(p)))
    if not candidates:
        return None
    # 동명 오버로드 다수 → 매개변수 적은 첫 항목 선택 (간단 휴리스틱)
    candidates.sort(key=lambda x: len(x.parameters))
    return candidates[0]


def summarize_for_llm(info: JavaMethodInfo) -> str:
    """LLM prompt 에 그대로 넣기 위한 요약 (시그니처 + 필드 + body)."""
    fields = "\n".join(f"  - {t} {n}" for t, n in info.class_fields)
    imports_short = "\n".join(f"  import {i}" for i in info.imports[:30])  # 처음 30개만
    params = ", ".join(f"{t} {n}" for t, n in info.parameters)
    return (
        f"// FILE: {info.file_path}\n"
        f"// PACKAGE: {info.package}\n"
        f"// CLASS: {info.class_name}\n"
        f"// FIELDS:\n{fields or '  (none)'}\n"
        f"// IMPORTS:\n{imports_short or '  (none)'}\n"
        f"// JAVADOC:\n{info.javadoc or '  (none)'}\n"
        f"// SIGNATURE: {' '.join(info.modifiers)} {info.return_type} {info.method_name}({params})\n"
        f"// BODY:\n{info.body_source}\n"
    )
