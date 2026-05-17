"""JavaToPythonTranspiler — Java method body_text → 실행 가능한 Python source.

설계 원칙:
- legacy `code-types/{class_fqn}` 의 `methods[].body_text` (Java source) 를 받아
  tree-sitter-java AST 로 파싱 → Python source 합성.
- subprocess 격리 실행을 위해 의존성 최소 (표준 Decimal 만 사용).
- 변환 미지원 노드는 `# TODO: <원본 Java>` 주석으로 남김 — LLM 후처리 가능.

지원 매핑 (1차):
- 변수 선언 (BigDecimal · String · int · boolean)
- 사칙연산 / 비교 / 논리
- if/else · for (literal 범위) · return
- BigDecimal API: multiply/add/subtract/divide → Decimal
- String API: length() / charAt(i) → len() / s[i]

미지원 (TODO 주석으로 노출):
- 사용자 정의 타입 (Entity, Service)
- try/catch
- 상속 호출 / Spring annotation

usage:
    transpiler = JavaToPythonTranspiler()
    py_src = transpiler.transpile(java_body_text, method_name="cumulativeProductivity")
"""

from __future__ import annotations

import logging
import re
from typing import Any

try:
    import tree_sitter_java  # type: ignore
    from tree_sitter import Language, Parser  # type: ignore
    _LANG = Language(tree_sitter_java.language())
    _PARSER = Parser(_LANG)
    _AVAILABLE = True
except Exception as e:  # pragma: no cover
    logging.getLogger(__name__).warning("tree-sitter-java 로드 실패: %s — transpiler 비활성", e)
    _PARSER = None
    _AVAILABLE = False

logger = logging.getLogger(__name__)

INDENT = "    "


class JavaToPythonTranspiler:
    """Java body_text → Python source.

    PoC 수준 — 일반 메서드의 일부 패턴만 변환. 미지원 노드는 주석으로 표시.
    완전 변환은 LLM 보조로 후처리하는 것이 권장.
    """

    available = _AVAILABLE

    def transpile(
        self,
        java_body: str,
        method_name: str = "method",
        params: list[dict[str, Any]] | None = None,
        return_type: str | None = None,
        class_fields: list[dict[str, Any]] | None = None,
        method_anchors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """전체 변환 entrypoint.

        Returns:
            {
              "python_source": str,      # 실행 가능한 Python module
              "function_name": str,
              "param_names": list[str],
              "warnings": list[str],     # 미지원 노드 발견 위치
              "ast_dump": str,           # 디버그용 AST 요약
              "ok": bool,
            }
        """
        if not _AVAILABLE:
            return self._fallback_no_parser(java_body, method_name, params)

        # 메서드 body 만 받으면 wrapping 필요 (Java 는 메서드 단위 파싱이 안 됨 → class 안에 넣고 파싱)
        # 만약 이미 `public BigDecimal foo(...) { ... }` 같이 메서드 단위면 그대로 wrap.
        wrapper = self._wrap_method(java_body, method_name, params, return_type)
        try:
            tree = _PARSER.parse(wrapper.encode("utf-8"))
        except Exception as e:
            return {
                "ok": False,
                "python_source": f"# tree-sitter parse 실패: {e}\n",
                "function_name": method_name,
                "param_names": [p.get("name", f"p{i}") for i, p in enumerate(params or [])],
                "warnings": [f"parse error: {e}"],
                "ast_dump": "",
            }

        root = tree.root_node

        # 메서드 노드 찾기
        method_node = self._find_first(root, "method_declaration")
        if method_node is None:
            return {
                "ok": False,
                "python_source": "# method_declaration 노드를 찾지 못했습니다\n",
                "function_name": method_name,
                "param_names": [],
                "warnings": ["no method_declaration in AST"],
                "ast_dump": _dump(root),
            }

        ctx = _Ctx(wrapper.encode("utf-8"))
        py_body_lines, warnings = self._transpile_method(method_node, ctx)

        param_names = self._extract_param_names(method_node, ctx)
        signature = f"def {method_name}({', '.join(param_names)}):"
        header = "from decimal import Decimal\n\n"

        # class_fields → anchor_locator 의 "NAME = LITERAL" 패턴에서 초기값 추출
        # legacy code-types 가 field initializer 자체를 노출하지 않으므로 anchor 보조 활용.
        field_inits: dict[str, str] = {}
        for a in (method_anchors or []):
            loc = a.get("anchor_locator") or ""
            m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$", loc)
            if m:
                field_inits[m.group(1)] = m.group(2)

        field_lines: list[str] = []
        for f in (class_fields or []):
            if not isinstance(f, dict):
                continue
            fname = f.get("name")
            ftype = (f.get("type") or "").lower()
            init = (
                f.get("initializer")
                or f.get("default_value")
                or f.get("value")
                or field_inits.get(fname or "")
            )
            if not fname or init is None:
                # SCREAMING_SNAKE 같은 상수가 아니면 skip (instance field 는 main 에 잡힘)
                if fname and fname.isupper():
                    field_lines.append(f"{fname} = None  # TODO: legacy 가 initializer 미노출")
                continue
            py_init = self._translate_field_initializer(str(init), ftype)
            field_lines.append(f"{fname} = {py_init}")

        prelude = "\n".join(field_lines) + ("\n\n" if field_lines else "")
        py_src = header + prelude + signature + "\n" + "\n".join(INDENT + l for l in py_body_lines)

        return {
            "ok": True,
            "python_source": py_src,
            "function_name": method_name,
            "param_names": param_names,
            "warnings": warnings,
            "ast_dump": _dump(method_node, depth=2),
        }

    # ─── 내부 ─────────────────────────────────────────────────────

    def _wrap_method(
        self,
        body: str,
        method_name: str,
        params: list[dict[str, Any]] | None,
        return_type: str | None,
    ) -> str:
        """body 가 이미 method 단위면 그대로, 아니면 wrap."""
        s = body.strip()
        if re.match(r"^\s*(public|private|protected|static|final|\s)*\s*\w[\w\[\]<>,\s\.]*\s+\w+\s*\(", s):
            # 이미 메서드 시그니처 포함
            method_src = s
        else:
            # body 만 — 메서드로 감싸기
            param_str = (
                ", ".join(f"{p.get('type','Object')} {p.get('name', f'p{i}')}" for i, p in enumerate(params or []))
                if params else ""
            )
            rt = return_type or "Object"
            method_src = f"public {rt} {method_name}({param_str}) {{\n{s}\n}}"
        return f"public class Wrapper {{\n{method_src}\n}}"

    def _find_first(self, node, kind: str):
        if node.type == kind:
            return node
        for child in node.children:
            r = self._find_first(child, kind)
            if r:
                return r
        return None

    def _extract_param_names(self, method_node, ctx: "_Ctx") -> list[str]:
        names: list[str] = []
        for child in method_node.children:
            if child.type == "formal_parameters":
                for p in child.children:
                    if p.type == "formal_parameter":
                        for c in p.children:
                            if c.type == "identifier":
                                names.append(ctx.text(c))
                                break
        return names

    def _transpile_method(self, method_node, ctx: "_Ctx") -> tuple[list[str], list[str]]:
        """method body 의 statements 를 Python lines 로 변환."""
        body_node = next((c for c in method_node.children if c.type == "block"), None)
        if body_node is None:
            return ["pass  # empty body"], []
        lines, warnings = self._transpile_block(body_node, ctx, indent=0)
        if not lines:
            lines = ["pass"]
        return lines, warnings

    def _transpile_block(self, block_node, ctx: "_Ctx", indent: int) -> tuple[list[str], list[str]]:
        lines: list[str] = []
        warnings: list[str] = []
        for stmt in block_node.children:
            if stmt.type in ("{", "}"):
                continue
            sub_lines, sub_warn = self._transpile_stmt(stmt, ctx, indent)
            lines.extend(sub_lines)
            warnings.extend(sub_warn)
        return lines, warnings

    def _transpile_stmt(self, node, ctx: "_Ctx", indent: int) -> tuple[list[str], list[str]]:
        kind = node.type
        warn: list[str] = []

        if kind == "local_variable_declaration":
            return self._local_var(node, ctx), warn

        if kind == "expression_statement":
            expr = node.children[0] if node.children else node
            return [self._expr(expr, ctx) + ""], warn

        if kind == "return_statement":
            val = next((c for c in node.children if c.type not in (";", "return")), None)
            return [f"return {self._expr(val, ctx) if val else 'None'}"], warn

        if kind == "if_statement":
            return self._if(node, ctx, indent)

        if kind == "for_statement":
            return self._for(node, ctx, indent)

        if kind == "while_statement":
            cond_node = node.child_by_field_name("condition")
            body_node = node.child_by_field_name("body")
            cond = self._expr(cond_node, ctx) if cond_node else "True"
            sub, w = self._transpile_block_or_stmt(body_node, ctx)
            warn.extend(w)
            return [f"while {cond}:", *[INDENT + s for s in sub]], warn

        if kind == "block":
            sub, w = self._transpile_block(node, ctx, indent)
            return sub, w

        if kind in (";", "comment", "line_comment", "block_comment"):
            return [], warn

        if kind == "continue_statement":
            return ["continue"], warn
        if kind == "break_statement":
            return ["break"], warn

        # 미지원
        warn.append(f"미지원 노드 type={kind} (line {node.start_point[0]+1}): {ctx.text(node)[:60]!r}")
        return [f"# TODO: {ctx.text(node)}"], warn

    def _transpile_block_or_stmt(self, node, ctx: "_Ctx") -> tuple[list[str], list[str]]:
        if node is None:
            return ["pass"], []
        if node.type == "block":
            lines, w = self._transpile_block(node, ctx, 0)
        else:
            lines, w = self._transpile_stmt(node, ctx, 0)
        if not lines:
            lines = ["pass"]
        return lines, w

    def _local_var(self, node, ctx: "_Ctx") -> list[str]:
        """`BigDecimal x = 0.95;` → `x = Decimal('0.95')`."""
        # children: type, variable_declarator (= identifier [= initializer])
        var_decl = next((c for c in node.children if c.type == "variable_declarator"), None)
        if not var_decl:
            return [f"# {ctx.text(node)}"]
        name = ""
        init = "None"
        for c in var_decl.children:
            if c.type == "identifier":
                name = ctx.text(c)
            elif c.type not in ("=", ";"):
                init = self._expr(c, ctx)
        return [f"{name} = {init}"]

    def _if(self, node, ctx: "_Ctx", indent: int) -> tuple[list[str], list[str]]:
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        cond_py = self._expr(cond, ctx) if cond else "True"
        cons_lines, w1 = self._transpile_block_or_stmt(cons, ctx)
        out = [f"if {cond_py}:", *[INDENT + l for l in cons_lines]]
        warnings = list(w1)
        if alt:
            if alt.type == "if_statement":
                alt_lines, w2 = self._if(alt, ctx, indent)
                out.append("el" + alt_lines[0])  # "if cond:" → "elif cond:"
                out.extend(alt_lines[1:])
                warnings.extend(w2)
            else:
                else_lines, w2 = self._transpile_block_or_stmt(alt, ctx)
                out.append("else:")
                out.extend(INDENT + l for l in else_lines)
                warnings.extend(w2)
        return out, warnings

    def _for(self, node, ctx: "_Ctx", indent: int) -> tuple[list[str], list[str]]:
        """`for (int i = 0; i < N; ++i)` → `for i in range(N):`."""
        init = node.child_by_field_name("init")
        cond = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        m = None
        if init and cond:
            init_txt = ctx.text(init)
            cond_txt = ctx.text(cond)
            m_init = re.search(r"\w+\s+(\w+)\s*=\s*([^,;]+)", init_txt)
            m_cond = re.search(r"(\w+)\s*<\s*([^;\)]+)", cond_txt)
            if m_init and m_cond:
                var = m_init.group(1)
                start = m_init.group(2).strip()
                end = m_cond.group(2).strip()
                sub, w = self._transpile_block_or_stmt(body, ctx)
                return [f"for {var} in range({start}, {end}):", *[INDENT + l for l in sub]], w
        sub, w = self._transpile_block_or_stmt(body, ctx)
        return [f"# TODO: unsupported for-loop\n{ctx.text(init) if init else ''} {ctx.text(cond) if cond else ''}", *sub], w

    def _expr(self, node, ctx: "_Ctx") -> str:
        if node is None:
            return ""
        kind = node.type
        text = ctx.text(node)
        if kind == "identifier" or kind == "this":
            return text
        if kind == "decimal_integer_literal":
            return text
        if kind == "decimal_floating_point_literal":
            return text
        if kind == "string_literal":
            return text  # Java "abc" → Python "abc" (대부분 호환)
        if kind == "character_literal":
            return text.replace("'", '"')
        if kind == "true":
            return "True"
        if kind == "false":
            return "False"
        if kind == "null_literal" or text == "null":
            return "None"
        if kind == "parenthesized_expression":
            inner_node = next((c for c in node.children if c.type not in ("(", ")")), None)
            return f"({self._expr(inner_node, ctx)})" if inner_node else "()"
        if kind == "binary_expression":
            return self._binary(node, ctx)
        if kind == "unary_expression":
            op = node.child(0)
            opnd = node.child(1)
            op_t = ctx.text(op)
            mapped = {"!": "not ", "-": "-", "+": "+"}.get(op_t, op_t)
            return f"{mapped}{self._expr(opnd, ctx)}"
        if kind == "update_expression":
            return self._update_expr(node, ctx)
        if kind == "method_invocation":
            return self._method_invocation(node, ctx)
        if kind == "field_access":
            return ".".join(ctx.text(c) for c in node.children if c.type not in (".",))
        if kind == "assignment_expression":
            return self._assignment(node, ctx)
        if kind == "object_creation_expression":
            return self._object_creation(node, ctx)
        if kind == "array_access":
            arr = node.child_by_field_name("array")
            idx = node.child_by_field_name("index")
            return f"{self._expr(arr, ctx)}[{self._expr(idx, ctx)}]"
        if kind == "ternary_expression":
            cond = node.child_by_field_name("condition")
            cons = node.child_by_field_name("consequence")
            alt = node.child_by_field_name("alternative")
            return f"({self._expr(cons, ctx)} if {self._expr(cond, ctx)} else {self._expr(alt, ctx)})"
        # fallback — 원본 Java 그대로
        return f"/* TODO {kind}: {text} */"

    def _binary(self, node, ctx: "_Ctx") -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op_node = node.child_by_field_name("operator") or node.children[1]
        op = ctx.text(op_node)
        op_map = {"&&": "and", "||": "or", "==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
                  "+": "+", "-": "-", "*": "*", "/": "/", "%": "%"}
        py_op = op_map.get(op, op)
        return f"{self._expr(left, ctx)} {py_op} {self._expr(right, ctx)}"

    def _update_expr(self, node, ctx: "_Ctx") -> str:
        """++i / i++ → i += 1."""
        target = next((c for c in node.children if c.type == "identifier"), None)
        if target:
            name = ctx.text(target)
            if "++" in ctx.text(node):
                return f"({name} := {name} + 1)"
            if "--" in ctx.text(node):
                return f"({name} := {name} - 1)"
        return ctx.text(node)

    def _method_invocation(self, node, ctx: "_Ctx") -> str:
        """`x.multiply(y)` → `x * y` 등 BigDecimal/String API 매핑."""
        obj = node.child_by_field_name("object")
        name = node.child_by_field_name("name")
        args_node = node.child_by_field_name("arguments")
        obj_py = self._expr(obj, ctx) if obj else ""
        method = ctx.text(name) if name else ""
        args = [self._expr(c, ctx) for c in args_node.children if c.type not in ("(", ")", ",")] if args_node else []

        # BigDecimal API
        bd_map = {"multiply": "*", "add": "+", "subtract": "-", "divide": "/"}
        if method in bd_map and args:
            return f"({obj_py} {bd_map[method]} {args[0]})"
        # String API
        if method == "length":
            return f"len({obj_py})"
        if method == "charAt" and args:
            return f"{obj_py}[{args[0]}]"
        if method == "equals" and args:
            return f"({obj_py} == {args[0]})"
        # 일반 호출
        if obj_py:
            return f"{obj_py}.{method}({', '.join(args)})"
        return f"{method}({', '.join(args)})"

    def _assignment(self, node, ctx: "_Ctx") -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op_node = node.child_by_field_name("operator") or node.children[1]
        op = ctx.text(op_node)
        return f"{self._expr(left, ctx)} {op} {self._expr(right, ctx)}"

    def _object_creation(self, node, ctx: "_Ctx") -> str:
        """`new BigDecimal("0.95")` → `Decimal("0.95")`."""
        type_node = node.child_by_field_name("type")
        args_node = node.child_by_field_name("arguments")
        type_name = ctx.text(type_node) if type_node else "Object"
        args = [self._expr(c, ctx) for c in args_node.children if c.type not in ("(", ")", ",")] if args_node else []
        if type_name == "BigDecimal":
            return f"Decimal({', '.join(args)})"
        return f"{type_name}({', '.join(args)})"

    def _translate_field_initializer(self, init_text: str, ftype: str) -> str:
        """Java field initializer (text) → Python literal/expression.

        e.g. `new BigDecimal("0.95")` → `Decimal("0.95")`
             `"abc"` → `"abc"`,  `8` → `8`,  `null` → `None`
        """
        s = init_text.strip().rstrip(";").strip()
        if s == "null":
            return "None"
        # `new BigDecimal("X")` → `Decimal("X")`
        m = re.match(r"^new\s+BigDecimal\s*\(\s*(.+?)\s*\)$", s)
        if m:
            return f"Decimal({m.group(1)})"
        # primitive / string literal 은 그대로
        return s

    def _fallback_no_parser(self, body: str, method_name: str, params: list[dict] | None) -> dict[str, Any]:
        names = [p.get("name", f"p{i}") for i, p in enumerate(params or [])]
        return {
            "ok": False,
            "python_source": f"# tree-sitter-java 비활성\ndef {method_name}({', '.join(names)}):\n    raise NotImplementedError('Java AST 파서 미설치')\n",
            "function_name": method_name,
            "param_names": names,
            "warnings": ["tree-sitter-java 미설치"],
            "ast_dump": "",
        }


# ─── 유틸 ──────────────────────────────────────────────────────────


class _Ctx:
    def __init__(self, source: bytes):
        self.source = source

    def text(self, node) -> str:
        return self.source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _dump(node, depth: int = 1, level: int = 0) -> str:
    if level > depth:
        return ""
    indent = "  " * level
    out = f"{indent}{node.type} [{node.start_point[0]+1}:{node.start_point[1]}-{node.end_point[0]+1}:{node.end_point[1]}]"
    return "\n".join([out] + [_dump(c, depth, level+1) for c in node.children if level+1 <= depth])


__all__ = ["JavaToPythonTranspiler"]
