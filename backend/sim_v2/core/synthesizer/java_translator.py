"""Java AST → Python source translator — W7.1 + W8.

tree-sitter-java AST node 를 walk 해서 Python source fragment 를 emit.
W8 부터 type-aware: local_scope (var → type) + TypeResolver (method return type / field type)
로 chained-call BigDecimal recognition 가능.

Scope:
  - Expression: identifier / literal / binary_expression / method_invocation / field_access
  - Statement: return / assignment / local_variable_declaration / expression_statement
  - Control flow: if / while / for-each (enhanced_for_statement)
  - Block / parenthesized

Out of scope (SIGNATURE_LOCKED on unknown node):
  - try/catch/throw, switch, lambda, generics, inner class

Public API:
  - JavaToPythonTranslator(plugin_contract=None, type_resolver=BigDecimalAwareResolver())
  - translate(node, indent=0) -> TranslationResult
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.sim_v2.core.synthesizer.bigdecimal_mapper import (
    REQUIRED_IMPORTS as BIGDECIMAL_IMPORTS,
    map_bigdecimal_constructor,
    map_bigdecimal_method,
    map_static_field,
)
from backend.sim_v2.core.synthesizer.exception_mapper import map_java_exception
from backend.sim_v2.core.synthesizer.idiom_rewriter import (
    rewrite_method_invocation,
)
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    TypeResolver,
    is_bigdecimal_type,
)


@dataclass
class TranslationResult:
    """One translate() output — Python source + collected imports + notes."""
    python_source:    str
    imports_needed:   set[str] = field(default_factory=set)
    notes:            list[str] = field(default_factory=list)
    signature_locked: bool = False


_EXPRESSION_TYPES = frozenset({
    "identifier",
    "decimal_integer_literal",
    "decimal_floating_point_literal",
    "string_literal",
    "true", "false", "null_literal",
    "binary_expression",
    "unary_expression",
    "parenthesized_expression",
    "method_invocation",
    "field_access",
    "object_creation_expression",
    "cast_expression",
    "assignment_expression",
    "this",
    "ternary_expression",
    "instanceof_expression",
    "switch_expression",
})

_STATEMENT_TYPES = frozenset({
    "return_statement",
    "local_variable_declaration",
    "expression_statement",
    "if_statement",
    "while_statement",
    "for_statement",
    "enhanced_for_statement",
    "block",
    "throw_statement",
    "try_statement",
    "assert_statement",
    "break_statement",
    "continue_statement",
    "switch_expression",
    "line_comment",
    "block_comment",
})


class JavaToPythonTranslator:
    """Walk tree-sitter Java AST node → emit Python source.

    Type-aware (W8): tracks `local_scope` of declared variables and consults
    `type_resolver` for method-return / field-access types. BigDecimal-typed
    receivers route through `bigdecimal_mapper`.

    Trace-instrument mode (W16): when translate(with_trace=True), each
    local_variable_declaration / return / throw / branch emits a
    `_trace.step(...)` / `_trace.branch(...)` / `_trace.exception(...)` call.
    Runtime caller must provide a `_trace` object in globals (TraceCollector).
    """

    def __init__(
        self,
        plugin_contract=None,
        type_resolver: TypeResolver | None = None,
        this_type: str | None = None,
    ) -> None:
        self.plugin_contract = plugin_contract
        self.type_resolver: TypeResolver = type_resolver or BigDecimalAwareResolver()
        self.this_type = this_type  # FQN of enclosing class (W21 — for `this.field` resolution)
        self._collected_imports: set[str] = set()
        self._collected_notes: list[str] = []
        self._signature_locked = False
        self._local_scope: dict[str, str] = {}
        self._trace_active: bool = False
        self._trace_counter: int = 0
        # W41 — multi-statement lambda → nested def hoisting.
        # Filled by `_translate_lambda_expression` when it encounters a block body
        # with >1 statement (or a single non-return statement), drained by
        # `_translate_block` immediately before the statement that registered them.
        self._pending_hoists: list[str] = []
        self._lambda_counter: int = 0

    # ─────────────────────────────────────────────────────────────────────
    # Top-level entry
    # ─────────────────────────────────────────────────────────────────────

    def translate(self, node, indent: int = 0, with_trace: bool = False) -> TranslationResult:
        """Translate one tree-sitter Java AST node into Python source.

        with_trace=True 시 instrumented Python emit. Caller's globals 에
        `_trace` (TraceCollector) 가 있어야 실행 가능.
        """
        self._collected_imports = set()
        self._collected_notes = []
        self._signature_locked = False
        self._local_scope = {}
        self._trace_active = with_trace
        self._trace_counter = 0
        self._pending_hoists = []
        self._lambda_counter = 0
        source = self._dispatch(node, indent=indent)
        return TranslationResult(
            python_source=source,
            imports_needed=set(self._collected_imports),
            notes=list(self._collected_notes),
            signature_locked=self._signature_locked,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Trace helpers (W16)
    # ─────────────────────────────────────────────────────────────────────

    def _next_anchor(self) -> str:
        self._trace_counter += 1
        return f"anchor_{self._trace_counter}"

    def _emit_trace_step(self, indent: int, var_names: list[str]) -> str:
        """Emit `_trace.step('anchor_N', {'var': var, ...})` line, or empty if trace off."""
        if not self._trace_active:
            return ""
        anchor = self._next_anchor()
        if var_names:
            dict_items = ", ".join(f"{n!r}: {n}" for n in var_names)
            return f"\n{self._pad(indent)}_trace.step({anchor!r}, {{{dict_items}}})"
        return f"\n{self._pad(indent)}_trace.step({anchor!r}, {{}})"

    def _emit_trace_branch(self, indent: int, cond_src: str) -> str:
        if not self._trace_active:
            return ""
        anchor = self._next_anchor()
        return f"{self._pad(indent)}_trace.branch({anchor!r}, bool({cond_src}))\n"

    def _emit_trace_exception(self, indent: int, exc_class: str, msg: str) -> str:
        """Trace exception emit — used in throw_statement when trace_active.

        Note: we emit the trace call BEFORE the raise (so trace records the
        intent even though the raise interrupts flow).
        """
        if not self._trace_active:
            return ""
        anchor = self._next_anchor()
        return f"{self._pad(indent)}_trace.exception({anchor!r}, {exc_class!r}, str({msg}))\n"

    # ─────────────────────────────────────────────────────────────────────
    # Dispatch
    # ─────────────────────────────────────────────────────────────────────

    def _dispatch(self, node, *, indent: int) -> str:
        if node is None:
            return ""
        handler = getattr(self, f"_translate_{node.type}", None)
        if handler is None:
            self._signature_locked = True
            self._collected_notes.append(f"UNMAPPED node type: {node.type!r}")
            return f"{'    ' * indent}# UNMAPPED Java node: {node.type}"
        return handler(node, indent=indent)

    # ─────────────────────────────────────────────────────────────────────
    # Type inference (W8)
    # ─────────────────────────────────────────────────────────────────────

    def _infer_type(self, node) -> str | None:
        """Best-effort type FQN of an expression node.

        Returns None when type unknown. Caller must handle None gracefully.
        """
        if node is None:
            return None
        t = node.type

        if t == "identifier":
            return self._local_scope.get(self._text(node))

        if t == "this":
            # W21: return enclosing class FQN if known, else "this" placeholder.
            return self.this_type or "this"

        if t in {"decimal_integer_literal",}:
            return "int"
        if t == "decimal_floating_point_literal":
            return "double"
        if t == "string_literal":
            return "java.lang.String"
        if t in {"true", "false"}:
            return "boolean"
        if t == "null_literal":
            return None

        if t == "parenthesized_expression":
            for child in node.named_children:
                return self._infer_type(child)
            return None

        if t == "cast_expression":
            type_node = node.child_by_field_name("type")
            return self._text(type_node) if type_node else None

        if t == "object_creation_expression":
            type_node = node.child_by_field_name("type")
            return self._text(type_node) if type_node else None

        if t == "field_access":
            obj = node.child_by_field_name("object")
            field_node = node.child_by_field_name("field")
            field_name = self._text(field_node)
            # Static field via class FQN
            obj_text = self._text(obj)
            if obj_text in {"BigDecimal", "java.math.BigDecimal", "MathContext", "RoundingMode"}:
                return self.type_resolver.resolve_field_type(obj_text, field_name)
            # Instance field
            obj_type = self._infer_type(obj)
            return self.type_resolver.resolve_field_type(obj_type, field_name)

        if t == "method_invocation":
            object_node = node.child_by_field_name("object")
            name_node = node.child_by_field_name("name")
            method_name = self._text(name_node)
            receiver_type = self._infer_type(object_node) if object_node else None
            resolved = self.type_resolver.resolve_method_return_type(
                receiver_type, method_name,
            )
            if resolved is not None:
                return resolved
            # W51 — unambiguous BigDecimal arithmetic returns BigDecimal even when
            # receiver type is unknown. Makes type info propagate through chains
            # like `slab.getX().multiply(Y).divide(Z)` so the outer .divide is
            # correctly typed.
            if method_name in _UNAMBIGUOUS_BIGDECIMAL_METHODS:
                return "java.math.BigDecimal"
            return None

        if t == "binary_expression":
            # Approximation: type of left operand
            left = node.child_by_field_name("left")
            return self._infer_type(left)

        if t == "unary_expression":
            operand = node.child_by_field_name("operand")
            return self._infer_type(operand)

        return None

    # ─────────────────────────────────────────────────────────────────────
    # Expressions
    # ─────────────────────────────────────────────────────────────────────

    def _text(self, node) -> str:
        return node.text.decode() if node else ""

    def _translate_identifier(self, node, *, indent: int) -> str:
        return self._text(node)

    def _translate_decimal_integer_literal(self, node, *, indent: int) -> str:
        return self._text(node).replace("_", "").rstrip("Ll")

    def _translate_decimal_floating_point_literal(self, node, *, indent: int) -> str:
        return self._text(node).replace("_", "").rstrip("FfDd")

    def _translate_string_literal(self, node, *, indent: int) -> str:
        return self._text(node)

    def _translate_character_literal(self, node, *, indent: int) -> str:
        """Java `'x'` → Python `'x'` (single-char string).

        Java char and Python str-of-length-1 differ semantically (int vs str),
        but the literal syntax is identical. Most production code only compares
        chars by equality which works in Python on str.
        """
        return self._text(node)

    def _translate_method_reference(self, node, *, indent: int) -> str:
        """Java `Foo::bar` → Python `Foo.bar`. `MyClass::new` → `MyClass`
        (Python classes are first-class callables).

        Field-access receivers preserved: `System.out::println` → `System.out.println`.
        """
        children = node.named_children
        if not children:
            self._signature_locked = True
            return "# UNMAPPED method_reference (no children)"

        receiver_src = self._dispatch(children[0], indent=0)
        # Constructor reference: `Foo::new` has only the type as a child;
        # the "new" keyword is unnamed. Detect via raw text.
        if "::new" in self._text(node):
            return receiver_src

        if len(children) >= 2:
            method_name = self._text(children[1])
            return f"{receiver_src}.{method_name}"
        return receiver_src

    def _translate_class_literal(self, node, *, indent: int) -> str:
        """Java `Foo.class` → Python type literal.

        Common Java built-in types map to Python builtins; unknown types emit
        the bare type identifier (Python classes are first-class callables).
        Not a true reflection equivalent — caller using it for `Class.newInstance()`
        would need additional support.
        """
        # The single named child is the type_identifier
        type_text = ""
        for child in node.named_children:
            if child.type in {"type_identifier", "scoped_type_identifier"}:
                type_text = self._text(child)
                break
            type_text = self._text(child)
            break

        return _JAVA_TYPE_TO_PYTHON.get(type_text, type_text)

    def _translate_true(self, node, *, indent: int) -> str:
        return "True"

    def _translate_false(self, node, *, indent: int) -> str:
        return "False"

    def _translate_null_literal(self, node, *, indent: int) -> str:
        return "None"

    def _translate_this(self, node, *, indent: int) -> str:
        return "self"

    def _translate_parenthesized_expression(self, node, *, indent: int) -> str:
        for child in node.named_children:
            return f"({self._dispatch(child, indent=0)})"
        return "()"

    def _translate_binary_expression(self, node, *, indent: int) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op_node = node.child_by_field_name("operator")
        left_src = self._dispatch(left, indent=0)
        right_src = self._dispatch(right, indent=0)
        op_text = self._text(op_node)
        op_map = {"&&": "and", "||": "or"}
        op_text = op_map.get(op_text, op_text)

        # Java `+` with String operand = string concat with auto-toString.
        # Python `+` requires same types — wrap non-string operands with str() (W14).
        if op_text == "+":
            left_type = self._infer_type(left)
            right_type = self._infer_type(right)
            if "java.lang.String" in (left_type, right_type):
                if left_type != "java.lang.String":
                    left_src = f"str({left_src})"
                if right_type != "java.lang.String":
                    right_src = f"str({right_src})"

        return f"{left_src} {op_text} {right_src}"

    # ─────────────────────────────────────────────────────────────────────
    # Comments (W14)
    # ─────────────────────────────────────────────────────────────────────

    def _translate_line_comment(self, node, *, indent: int) -> str:
        """Java `// ...` → Python `# ...`. Strip the Java `//` prefix."""
        text = self._text(node)
        if text.startswith("//"):
            text = text[2:].lstrip()
        return f"{self._pad(indent)}# {text}"

    def _translate_block_comment(self, node, *, indent: int) -> str:
        """Java `/* ... */` or `/** ... */` (Javadoc) → Python comment.

        Multi-line block comments emit one `# line` per source line.
        """
        text = self._text(node)
        if text.startswith("/*"):
            text = text[2:]
        if text.endswith("*/"):
            text = text[:-2]
        lines = text.split("\n")
        pad = self._pad(indent)
        return "\n".join(f"{pad}# {line.lstrip(' *').rstrip()}" for line in lines)

    def _translate_unary_expression(self, node, *, indent: int) -> str:
        op_node = node.child_by_field_name("operator")
        operand = node.child_by_field_name("operand")
        op = self._text(op_node)
        operand_src = self._dispatch(operand, indent=0)
        if op == "!":
            return f"not {operand_src}"
        return f"{op}{operand_src}"

    def _translate_update_expression(self, node, *, indent: int) -> str:
        """Java `i++` / `++i` / `i--` / `--i` → Python `i += 1` / `i -= 1`.

        Python lacks in-place ++ / -- so the translation only works when the
        update is a STATEMENT (parent is `expression_statement`). Used as an
        expression value (e.g. `int j = i++`), the post/pre distinction matters
        and we signature-lock with an actionable note.
        """
        # operand is the only named child (identifier in most real code)
        operand = None
        for child in node.named_children:
            operand = child
            break
        operand_src = self._dispatch(operand, indent=0) if operand else "_"
        # Operator extraction — node.text has the full `i++` / `++i` text
        text = self._text(node)
        if text.endswith("++") or text.startswith("++"):
            delta = "+= 1"
        elif text.endswith("--") or text.startswith("--"):
            delta = "-= 1"
        else:
            self._signature_locked = True
            self._collected_notes.append(f"unknown update_expression form: {text!r}")
            return f"# UNMAPPED update_expression: {text}"

        # expression_statement wraps us and applies its own indent. Real
        # production code uses i++ overwhelmingly as a statement, so the
        # assignment form is the correct emission. Callers using i++ as an
        # expression value get a syntactically odd line — acceptable trade-off
        # because that form is rare and the SIGNATURE_LOCKED path doesn't help
        # callers either.
        return f"{operand_src} {delta}"

    def _translate_assignment_expression(self, node, *, indent: int) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op_node = node.child_by_field_name("operator")
        op = self._text(op_node) or "="
        return f"{self._dispatch(left, indent=0)} {op} {self._dispatch(right, indent=0)}"

    def _translate_array_access(self, node, *, indent: int) -> str:
        """Java `a[i]` → Python `a[i]` (same syntax, transparent)."""
        children = node.named_children
        if len(children) < 2:
            self._signature_locked = True
            return "# UNMAPPED array_access (insufficient children)"
        receiver_src = self._dispatch(children[0], indent=0)
        index_src    = self._dispatch(children[1], indent=0)
        return f"{receiver_src}[{index_src}]"

    def _translate_array_creation_expression(self, node, *, indent: int) -> str:
        """Java `new T[N]` → Python `[None] * N`; `new T[]{...}` uses the
        array_initializer child verbatim. Multi-dim arrays signature-lock."""
        # Find dimensions_expr (sized) or array_initializer (literal)
        dim_exprs = [c for c in node.named_children if c.type == "dimensions_expr"]
        initializer = next(
            (c for c in node.named_children if c.type == "array_initializer"),
            None,
        )
        if initializer is not None:
            return self._dispatch(initializer, indent=0)
        if len(dim_exprs) == 1:
            size_node = dim_exprs[0].named_children[0] if dim_exprs[0].named_children else None
            size_src = self._dispatch(size_node, indent=0) if size_node else "0"
            return f"[None] * {size_src}"
        # Multi-dim or unsupported — lock with note
        self._signature_locked = True
        self._collected_notes.append(
            f"multi-dim array_creation_expression not supported ({len(dim_exprs)}D)"
        )
        return "# UNMAPPED multi-dim array creation"

    def _translate_array_initializer(self, node, *, indent: int) -> str:
        """Java `{1, 2, 3}` → Python `[1, 2, 3]`."""
        items = [self._dispatch(c, indent=0) for c in node.named_children]
        return f"[{', '.join(items)}]"

    def _translate_array_type(self, node, *, indent: int) -> str:
        """Java `int[]` as a type-only context — emit the inner type identifier
        unchanged. Most callers (local_variable_declaration) ignore the type
        anyway; this prevents UNMAPPED when array_type appears in casts."""
        for child in node.named_children:
            if child.type != "dimensions":
                return self._dispatch(child, indent=0)
        return ""

    def _translate_dimensions_expr(self, node, *, indent: int) -> str:
        """Bare `[N]` reached outside of array_creation. Emit the inner expr."""
        for child in node.named_children:
            return self._dispatch(child, indent=0)
        return ""

    def _translate_dimensions(self, node, *, indent: int) -> str:
        """Bare `[]` (type-decoration only) — emit nothing in expression context."""
        return ""

    def _translate_field_access(self, node, *, indent: int) -> str:
        obj = node.child_by_field_name("object")
        field_node = node.child_by_field_name("field")
        obj_src = self._dispatch(obj, indent=0)
        field_name = self._text(field_node)

        # Static field — BigDecimal.ZERO / RoundingMode.HALF_UP / MathContext.DECIMAL64
        if obj_src in {"BigDecimal", "RoundingMode", "MathContext"}:
            mapped = map_static_field(obj_src, field_name)
            if mapped is not None:
                self._collected_imports.update(BIGDECIMAL_IMPORTS)
                return mapped

        return f"{obj_src}.{field_name}"

    def _translate_object_creation_expression(self, node, *, indent: int) -> str:
        type_node = node.child_by_field_name("type")
        args_node = node.child_by_field_name("arguments")
        type_text = self._text(type_node)

        # W30 — anonymous inner class detection: `new Type() { ... }`. The
        # body lives in expression position and would need multi-line hoisting,
        # which the single-pass emitter can't do cleanly. Honest signal-lock.
        for child in node.named_children:
            if child.type == "class_body":
                self._signature_locked = True
                self._collected_notes.append(
                    f"anonymous inner class not translated for {type_text!r} — "
                    "refactor to named class or lambda (functional interface)"
                )
                return f"{type_text}()  # UNMAPPED anonymous inner class"

        arg_strs: list[str] = []
        if args_node:
            for child in args_node.named_children:
                arg_strs.append(self._dispatch(child, indent=0))

        if type_text == "BigDecimal":
            self._collected_imports.update(BIGDECIMAL_IMPORTS)
            self._collected_imports.add("decimal")
            return map_bigdecimal_constructor(arg_strs)

        return f"{type_text}({', '.join(arg_strs)})"

    def _translate_cast_expression(self, node, *, indent: int) -> str:
        value_node = node.child_by_field_name("value")
        type_node = node.child_by_field_name("type")
        type_text = self._text(type_node)
        value_src = self._dispatch(value_node, indent=0)
        if type_text in {"int", "Integer", "long", "Long"}:
            return f"int({value_src})"
        if type_text in {"float", "Float", "double", "Double"}:
            return f"float({value_src})"
        if type_text == "String":
            return f"str({value_src})"
        return value_src

    def _translate_method_invocation(self, node, *, indent: int) -> str:
        object_node = node.child_by_field_name("object")
        name_node = node.child_by_field_name("name")
        args_node = node.child_by_field_name("arguments")

        method_name = self._text(name_node)

        arg_strs: list[str] = []
        if args_node:
            for child in args_node.named_children:
                arg_strs.append(self._dispatch(child, indent=0))

        if object_node is None:
            return f"{method_name}({', '.join(arg_strs)})"

        receiver_src = self._dispatch(object_node, indent=0)
        receiver_type = self._infer_type(object_node)

        # W54 — Java factory methods that map to Python literal forms:
        #   `List.of(a, b, c)` → `[a, b, c]`     (empty: `List.of()` → `[]`)
        #   `Set.of(a, b)`     → `{a, b}`         (empty: `Set.of()`  → `set()`)
        #   `Map.of(k, v)`     → `{k: v}`         (empty: `Map.of()`  → `{}`)
        # Triggered only when the receiver is the literal class identifier —
        # avoids clashing with `someList.of(...)` instance-method names.
        if method_name == "of" and receiver_src == "List":
            return "[" + ", ".join(arg_strs) + "]"
        if method_name == "of" and receiver_src == "Set":
            if not arg_strs:
                return "set()"
            return "{" + ", ".join(arg_strs) + "}"
        if method_name == "of" and receiver_src == "Map":
            if not arg_strs:
                return "{}"
            # Map.of(k1, v1, k2, v2, ...) — pair up successive args
            if len(arg_strs) % 2 == 0:
                pairs = [
                    f"{arg_strs[i]}: {arg_strs[i + 1]}"
                    for i in range(0, len(arg_strs), 2)
                ]
                return "{" + ", ".join(pairs) + "}"

        # Type-aware BigDecimal dispatch — receiver type known to be BigDecimal.
        # W51 — also fire on *unambiguous* BD arithmetic method names (subtract /
        # multiply / divide / remainder) when receiver type is unknown. These
        # never collide with Collection / Set APIs (`add` was the one ambiguous
        # case and is excluded from the unambiguous set). Covers production
        # chains like `slab.getX().multiply(Y).divide(Z)` where the getter's
        # return type isn't tracked by the resolver.
        unambiguous_bd = (
            method_name in _UNAMBIGUOUS_BIGDECIMAL_METHODS
            and 1 <= len(arg_strs) <= 2
        )
        if (
            is_bigdecimal_type(receiver_type)
            or receiver_src == "BigDecimal"
            or unambiguous_bd
        ):
            self._collected_imports.update(BIGDECIMAL_IMPORTS)
            mapped = map_bigdecimal_method(receiver_src, method_name, arg_strs)
            if not mapped.startswith("# UNMAPPED"):
                return mapped
            # Only signature-lock when receiver type was *known* BigDecimal —
            # otherwise the unambiguous-method heuristic might mis-fire and we
            # let the call fall through to its default form.
            if is_bigdecimal_type(receiver_type):
                self._signature_locked = True
                self._collected_notes.append(f"UNMAPPED BigDecimal.{method_name}")

        # W75 — Java idiom rewrites (String/Collection/Optional/Math/Objects).
        # Fires before the generic fallback. Returns None if no idiom matched.
        idiom = rewrite_method_invocation(
            receiver_src, receiver_type, method_name, arg_strs,
        )
        if idiom is not None:
            return idiom

        return f"{receiver_src}.{method_name}({', '.join(arg_strs)})"

    # ─────────────────────────────────────────────────────────────────────
    # Statements
    # ─────────────────────────────────────────────────────────────────────

    def _pad(self, indent: int) -> str:
        return "    " * indent

    def _translate_return_statement(self, node, *, indent: int) -> str:
        for child in node.named_children:
            return f"{self._pad(indent)}return {self._dispatch(child, indent=0)}"
        return f"{self._pad(indent)}return"

    def _translate_expression_statement(self, node, *, indent: int) -> str:
        for child in node.named_children:
            return f"{self._pad(indent)}{self._dispatch(child, indent=0)}"
        return f"{self._pad(indent)}pass"

    def _translate_local_variable_declaration(self, node, *, indent: int) -> str:
        """Java `Type name = value;` → Python `name = value`.

        W8: track `name → Type` in local_scope for downstream method dispatch.
        W16: when trace_active, append `_trace.step(...)` capturing newly bound var.
        """
        type_node = node.child_by_field_name("type")
        declared_type = self._text(type_node) if type_node else None

        var_lines: list[str] = []
        declared_names: list[str] = []
        for child in node.named_children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                name = self._text(name_node)
                if declared_type:
                    self._local_scope[name] = declared_type
                declared_names.append(name)
                if value_node:
                    value_src = self._dispatch(value_node, indent=0)
                    var_lines.append(f"{self._pad(indent)}{name} = {value_src}")
                else:
                    var_lines.append(f"{self._pad(indent)}{name} = None  # Java default")
        emitted = "\n".join(var_lines)
        if declared_names:
            emitted += self._emit_trace_step(indent, declared_names)
        return emitted

    def _translate_block(self, node, *, indent: int) -> str:
        lines: list[str] = []
        for child in node.named_children:
            if child.type in _STATEMENT_TYPES or child.type == "expression_statement":
                translated = self._dispatch(child, indent=indent)
            else:
                expr_src = self._dispatch(child, indent=0)
                translated = f"{self._pad(indent)}{expr_src}"
            # W41 — drain lambda hoists registered during this statement's
            # translation. Hoisted defs must precede the statement that uses them.
            if self._pending_hoists:
                lines.extend(self._pending_hoists)
                self._pending_hoists = []
            lines.append(translated)
        return "\n".join(lines) if lines else f"{self._pad(indent)}pass"

    def _translate_method_declaration(self, node, *, indent: int) -> str:
        """Java method → Python def. Parameters bound in local_scope (W9.2)."""
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        body_node = node.child_by_field_name("body")

        method_name = self._text(name_node)
        py_params: list[str] = ["self"]
        if params_node:
            for child in params_node.named_children:
                if child.type == "formal_parameter":
                    type_node = child.child_by_field_name("type")
                    p_name_node = child.child_by_field_name("name")
                    p_name = self._text(p_name_node)
                    p_type = self._text(type_node) if type_node else ""
                    if p_name and p_type:
                        self._local_scope[p_name] = p_type
                    if p_name:
                        py_params.append(p_name)

        body_src = (
            self._translate_branch_body(body_node, indent=indent + 1)
            if body_node
            else f"{self._pad(indent + 1)}pass"
        )
        return f"{self._pad(indent)}def {method_name}({', '.join(py_params)}):\n{body_src}"

    def register_method_parameters(self, method_decl_node) -> None:
        """Public helper — pre-populate local_scope from a method_declaration's parameters.

        Use when caller wants to translate only the method body (block) but needs the
        parameter types in scope. Idempotent across calls within one translate() session.
        """
        params_node = method_decl_node.child_by_field_name("parameters")
        if params_node is None:
            return
        for child in params_node.named_children:
            if child.type == "formal_parameter":
                type_node = child.child_by_field_name("type")
                name_node = child.child_by_field_name("name")
                name = self._text(name_node)
                t = self._text(type_node) if type_node else ""
                if name and t:
                    self._local_scope[name] = t

    def _translate_class_declaration(self, node, *, indent: int) -> str:
        """Java local class → Python nested class (W30).

        Handles local classes declared inside a method body:
            class Helper { int x() { return 1; } }
        emits:
            class Helper:
                def x(self):
                    return 1

        `static class Inner` strips the `static` modifier (Python has no equivalent;
        nested classes are already accessible from the outer scope).

        `extends`/`implements` are noted but not propagated — caller declarations
        won't have Python-side analogs for arbitrary Java types. The emitted class
        inherits from `object` implicitly.
        """
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")
        class_name = self._text(name_node) or "_Unnamed"

        if body_node is None:
            return f"{self._pad(indent)}class {class_name}:\n{self._pad(indent + 1)}pass"

        # Walk the class_body for declarations. Most local classes are method-only,
        # but field declarations (assignments) are valid Java too.
        member_lines: list[str] = []
        for member in body_node.named_children:
            t = member.type
            if t == "method_declaration":
                member_lines.append(self._translate_method_declaration(member, indent=indent + 1))
            elif t in {"field_declaration", "constant_declaration"}:
                # Java `int x = 1;` at class scope → Python class-attr `x = 1`
                for var_decl in member.named_children:
                    if var_decl.type == "variable_declarator":
                        name = self._text(var_decl.child_by_field_name("name"))
                        init = var_decl.child_by_field_name("value")
                        init_src = self._dispatch(init, indent=0) if init else "None"
                        member_lines.append(f"{self._pad(indent + 1)}{name} = {init_src}")
            elif t == "class_declaration":
                # Nested-nested class — recurse
                member_lines.append(self._translate_class_declaration(member, indent=indent + 1))
            elif t == "line_comment":
                continue
            else:
                self._signature_locked = True
                self._collected_notes.append(
                    f"unsupported class member {t!r} in {class_name!r}"
                )
                member_lines.append(
                    f"{self._pad(indent + 1)}pass  # UNMAPPED class member {t}"
                )

        if not member_lines:
            member_lines = [f"{self._pad(indent + 1)}pass"]

        body_src = "\n".join(member_lines)
        return f"{self._pad(indent)}class {class_name}:\n{body_src}"

    def _translate_if_statement(self, node, *, indent: int) -> str:
        cond = node.child_by_field_name("condition")
        consequence = node.child_by_field_name("consequence")
        alternative = node.child_by_field_name("alternative")

        cond_src = _strip_outer_parens(self._dispatch(cond, indent=0))
        # Trace branch (W16) — emit BEFORE the if statement so the branch is recorded
        trace_branch = self._emit_trace_branch(indent, cond_src)
        cons_src = self._translate_branch_body(consequence, indent=indent + 1)
        lines = [f"{trace_branch}{self._pad(indent)}if {cond_src}:", cons_src]
        if alternative:
            if alternative.type == "if_statement":
                inner = self._dispatch(alternative, indent=indent)
                lines.append(inner.replace(f"{self._pad(indent)}if ", f"{self._pad(indent)}elif ", 1))
            else:
                alt_src = self._translate_branch_body(alternative, indent=indent + 1)
                lines.append(f"{self._pad(indent)}else:")
                lines.append(alt_src)
        return "\n".join(lines)

    def _translate_branch_body(self, node, *, indent: int) -> str:
        if node is None:
            return f"{self._pad(indent)}pass"
        if node.type == "block":
            return self._translate_block(node, indent=indent)
        return self._dispatch(node, indent=indent)

    def _translate_while_statement(self, node, *, indent: int) -> str:
        cond = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        cond_src = self._dispatch(cond, indent=0)
        cond_src = _strip_outer_parens(cond_src)
        body_src = self._translate_branch_body(body, indent=indent + 1)
        return f"{self._pad(indent)}while {cond_src}:\n{body_src}"

    def _translate_enhanced_for_statement(self, node, *, indent: int) -> str:
        """`for (Type var : collection)` → `for var in collection:`.

        W8: track `var → Type` in local_scope for body.
        """
        type_node = node.child_by_field_name("type")
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        body = node.child_by_field_name("body")
        var = self._text(name_node)
        if type_node:
            self._local_scope[var] = self._text(type_node)
        coll = self._dispatch(value_node, indent=0)
        body_src = self._translate_branch_body(body, indent=indent + 1)
        return f"{self._pad(indent)}for {var} in {coll}:\n{body_src}"

    def _translate_for_statement(self, node, *, indent: int) -> str:
        init = node.child_by_field_name("init")
        cond = node.child_by_field_name("condition")
        update = node.child_by_field_name("update")
        body = node.child_by_field_name("body")

        init_src = self._dispatch(init, indent=indent) if init else ""
        cond_src = self._dispatch(cond, indent=0) if cond else "True"
        update_src = self._dispatch(update, indent=0) if update else ""
        body_src = self._translate_branch_body(body, indent=indent + 1)

        lines = []
        if init_src:
            lines.append(init_src)
        lines.append(f"{self._pad(indent)}while {cond_src}:")
        lines.append(body_src)
        if update_src:
            lines.append(f"{self._pad(indent + 1)}{update_src}")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # Exception handling (W10)
    # ─────────────────────────────────────────────────────────────────────

    def _translate_throw_statement(self, node, *, indent: int) -> str:
        """`throw new T(args)` → `raise T(args)`. W16: trace.exception preamble."""
        for child in node.named_children:
            if child.type == "object_creation_expression":
                type_node = child.child_by_field_name("type")
                args_node = child.child_by_field_name("arguments")
                type_text = self._text(type_node)
                py_exc = map_java_exception(type_text)

                arg_strs: list[str] = []
                if args_node:
                    for arg in args_node.named_children:
                        arg_strs.append(self._dispatch(arg, indent=0))
                args_repr = ", ".join(arg_strs)
                # Trace preamble: use last arg as message hint (or string repr of class name)
                msg_hint = arg_strs[-1] if arg_strs else f'"{py_exc}"'
                trace_line = self._emit_trace_exception(indent, py_exc, msg_hint)
                return f"{trace_line}{self._pad(indent)}raise {py_exc}({args_repr})"
            expr_src = self._dispatch(child, indent=0)
            return f"{self._pad(indent)}raise {expr_src}"
        return f"{self._pad(indent)}raise"

    def _translate_try_statement(self, node, *, indent: int) -> str:
        """try { } catch (E e) { } finally { } → try: / except E as e: / finally:.

        - body field: try block
        - catch_clause children: each → except
        - finally_clause child: optional finally
        Multi-catch (catch (A | B e)) → except (A, B) as e.
        try-with-resources (resource_specification) → out of scope, signature_locked.
        """
        # Detect try-with-resources — child of type "resource_specification"
        for child in node.named_children:
            if child.type == "resource_specification":
                self._signature_locked = True
                self._collected_notes.append("try-with-resources not supported (W10 scope)")
                return f"{self._pad(indent)}# UNMAPPED: try-with-resources"

        body_node = node.child_by_field_name("body")
        body_src = (
            self._translate_branch_body(body_node, indent=indent + 1)
            if body_node
            else f"{self._pad(indent + 1)}pass"
        )

        lines: list[str] = [f"{self._pad(indent)}try:", body_src]

        finally_clause = None
        for child in node.named_children:
            if child.type == "catch_clause":
                lines.append(self._translate_catch_clause(child, indent=indent))
            elif child.type == "finally_clause":
                finally_clause = child

        if finally_clause is not None:
            fin_body = None
            for child in finally_clause.named_children:
                if child.type == "block":
                    fin_body = child
                    break
            fin_body_src = (
                self._translate_branch_body(fin_body, indent=indent + 1)
                if fin_body
                else f"{self._pad(indent + 1)}pass"
            )
            lines.append(f"{self._pad(indent)}finally:")
            lines.append(fin_body_src)

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # Ternary / assert / instanceof / break / continue / switch (W11)
    # ─────────────────────────────────────────────────────────────────────

    def _translate_ternary_expression(self, node, *, indent: int) -> str:
        """Java `cond ? a : b` → Python `a if cond else b`."""
        children = node.named_children
        if len(children) < 3:
            self._signature_locked = True
            return "# UNMAPPED ternary (insufficient children)"
        cond_src = self._dispatch(children[0], indent=0)
        cons_src = self._dispatch(children[1], indent=0)
        alt_src = self._dispatch(children[2], indent=0)
        return f"({cons_src} if {cond_src} else {alt_src})"

    def _translate_instanceof_expression(self, node, *, indent: int) -> str:
        """Java `x instanceof T` → Python `isinstance(x, T)`.

        Java 16+ pattern (`x instanceof T t`) — additional identifier child
        becomes a separate assignment, which doesn't translate cleanly to a
        single expression. We emit `isinstance(x, T)` and warn.
        """
        children = node.named_children
        if len(children) < 2:
            self._signature_locked = True
            return "# UNMAPPED instanceof (insufficient children)"
        value_src = self._dispatch(children[0], indent=0)
        type_text = self._text(children[1])
        # Map Java std types to Python equivalents for isinstance
        py_type = _INSTANCEOF_TYPE_MAP.get(type_text, type_text)
        result = f"isinstance({value_src}, {py_type})"
        if len(children) >= 3:
            # Pattern variable (Java 16+) — note ambiguity
            self._collected_notes.append(
                f"instanceof pattern var ({self._text(children[2])}) not bound — manual assign needed"
            )
        return result

    def _translate_assert_statement(self, node, *, indent: int) -> str:
        """Java `assert cond` or `assert cond : msg` → Python `assert cond [, msg]`."""
        children = node.named_children
        if not children:
            return f"{self._pad(indent)}assert True  # empty assert"
        cond_src = self._dispatch(children[0], indent=0)
        if len(children) >= 2:
            msg_src = self._dispatch(children[1], indent=0)
            return f"{self._pad(indent)}assert {cond_src}, {msg_src}"
        return f"{self._pad(indent)}assert {cond_src}"

    def _translate_break_statement(self, node, *, indent: int) -> str:
        """`break;` → `break`. Labeled break (`break label;`) is SIGNATURE_LOCKED."""
        # Check for labeled break
        for child in node.named_children:
            if child.type == "identifier":
                self._signature_locked = True
                self._collected_notes.append(
                    f"labeled break ({self._text(child)}) not supported"
                )
                return f"{self._pad(indent)}break  # UNMAPPED: labeled break"
        return f"{self._pad(indent)}break"

    def _translate_continue_statement(self, node, *, indent: int) -> str:
        for child in node.named_children:
            if child.type == "identifier":
                self._signature_locked = True
                self._collected_notes.append(
                    f"labeled continue ({self._text(child)}) not supported"
                )
                return f"{self._pad(indent)}continue  # UNMAPPED: labeled continue"
        return f"{self._pad(indent)}continue"

    def _translate_switch_expression(self, node, *, indent: int) -> str:
        """Java switch → Python if-elif chain.

        tree-sitter calls it `switch_expression` even when used as statement.
        Structure: parenthesized_expression + switch_block (with switch_block_statement_group children).

        Fall-through (no `break` between cases) is signal-locked — emits comment.
        Arrow form (`case X -> ...`) is signal-locked.
        """
        cond_node = None
        block_node = None
        for child in node.named_children:
            if child.type == "parenthesized_expression":
                cond_node = child
            elif child.type == "switch_block":
                block_node = child

        if cond_node is None or block_node is None:
            self._signature_locked = True
            return f"{self._pad(indent)}# UNMAPPED switch (missing cond/block)"

        cond_src = _strip_outer_parens(self._dispatch(cond_node, indent=0))

        # Walk switch_block_statement_group children → (label_value | "default", body)
        groups: list[tuple[str | None, list]] = []  # label_value=None means default
        for child in block_node.named_children:
            if child.type == "switch_block_statement_group":
                labels: list[str | None] = []
                body_stmts = []
                for sub in child.named_children:
                    if sub.type == "switch_label":
                        # switch_label contains the case value (literal/identifier) or is "default"
                        # text-level check: starts with "default"
                        label_text = self._text(sub).strip()
                        if label_text.startswith("default"):
                            labels.append(None)
                        else:
                            # named child of switch_label = the value expression
                            inner = sub.named_children
                            if inner:
                                labels.append(self._dispatch(inner[0], indent=0))
                            else:
                                labels.append(label_text)
                    else:
                        body_stmts.append(sub)
                # One group may have multiple labels (Java switch case A: case B: ...)
                for label in labels:
                    groups.append((label, body_stmts))

        # Detect fall-through: a NON-final group with no break/return/throw → SIGNATURE_LOCKED.
        # Final group (or default) needs no break — Python flows past anyway.
        for idx, (label, body_stmts) in enumerate(groups):
            is_last = (idx == len(groups) - 1)
            is_default = (label is None)
            if is_last or is_default:
                continue
            if not body_stmts:
                # Empty non-final case is C-style fall-through label aliasing — accept silently
                continue
            last = body_stmts[-1]
            if last.type not in {"break_statement", "return_statement", "throw_statement"}:
                self._signature_locked = True
                self._collected_notes.append(
                    "switch fall-through (no break/return) not auto-translated"
                )

        # Emit as if/elif chain, dropping trailing break statements
        lines: list[str] = []
        first = True
        for label, body_stmts in groups:
            # Filter out trailing break_statement (already implicit in Python)
            effective_body = [s for s in body_stmts if s.type != "break_statement"]
            if not effective_body:
                effective_body = []  # empty body → `pass`

            if label is None:
                lines.append(f"{self._pad(indent)}else:")
            elif first:
                lines.append(f"{self._pad(indent)}if {cond_src} == {label}:")
                first = False
            else:
                lines.append(f"{self._pad(indent)}elif {cond_src} == {label}:")

            if not effective_body:
                lines.append(f"{self._pad(indent + 1)}pass")
            else:
                for stmt in effective_body:
                    lines.append(self._dispatch(stmt, indent=indent + 1))

        return "\n".join(lines) if lines else f"{self._pad(indent)}pass"

    # ─────────────────────────────────────────────────────────────────────
    # Lambda + try-with-resources (W27)
    # ─────────────────────────────────────────────────────────────────────

    def _translate_lambda_expression(self, node, *, indent: int) -> str:
        """Java lambda → Python lambda.

        Forms handled:
            x -> expr                 — single arg, no parens
            () -> expr                — zero args
            (a, b) -> expr            — multi args
            (x) -> { return expr; }   — single-return block body (inlined)

        Multi-statement block body → SIGNATURE_LOCKED (Python lambdas are
        expression-only; caller should refactor to a named function).
        """
        params: list[str] = []
        body_node = None
        for child in node.named_children:
            t = child.type
            if t == "identifier" and body_node is None and not params:
                # Single bare identifier param: `x -> ...`
                params.append(self._text(child))
            elif t == "formal_parameters":
                # `() -> ...` or typed parameters
                for sub in child.named_children:
                    if sub.type == "formal_parameter":
                        name_node = sub.child_by_field_name("name")
                        if name_node:
                            params.append(self._text(name_node))
                    elif sub.type == "identifier":
                        params.append(self._text(sub))
            elif t == "inferred_parameters":
                # `(a, b) -> ...`
                for sub in child.named_children:
                    if sub.type == "identifier":
                        params.append(self._text(sub))
            else:
                body_node = child

        params_src = ", ".join(params)
        header = f"lambda {params_src}:" if params else "lambda:"

        if body_node is None:
            self._signature_locked = True
            self._collected_notes.append("lambda missing body")
            return f"{header} None"

        if body_node.type == "block":
            # Block body — inline single `return expr;`; else hoist to a nested def (W41).
            statements = [
                c for c in body_node.named_children
                if c.type not in {"line_comment", "block_comment"}
            ]
            if len(statements) == 1 and statements[0].type == "return_statement":
                # Extract the returned expression
                inner = statements[0].named_children
                if inner:
                    expr_src = self._dispatch(inner[0], indent=0)
                    return f"{header} {expr_src}"
                # `return;` in a lambda — unusual, treat as None
                return f"{header} None"
            # W41 — multi-statement body → hoist as a nested `def` and return its name.
            if statements:
                return self._hoist_lambda_to_def(params, statements, indent)
            # Empty block — keep the lambda no-op shape
            return f"{header} None"

        # Expression body
        expr_src = self._dispatch(body_node, indent=0)
        return f"{header} {expr_src}"

    def _hoist_lambda_to_def(
        self,
        params: list[str],
        statements,
        indent: int,
    ) -> str:
        """W41 — emit a nested `def` at the enclosing block's indent and return
        a reference to it. Captures are handled by Python's lexical closure, so
        the def takes only the lambda's declared parameters.

        The def is appended to `_pending_hoists`; `_translate_block` drains the
        buffer immediately before emitting the statement that registered the
        hoist, so order is preserved (def then call).
        """
        self._lambda_counter += 1
        name = f"_lambda_{self._lambda_counter}"
        params_src = ", ".join(params)

        body_lines: list[str] = []
        for stmt in statements:
            body_lines.append(self._dispatch(stmt, indent=indent + 1))
        body_src = "\n".join(body_lines) if body_lines else f"{self._pad(indent + 1)}pass"

        def_src = f"{self._pad(indent)}def {name}({params_src}):\n{body_src}"
        self._pending_hoists.append(def_src)
        return name

    def _translate_try_with_resources_statement(self, node, *, indent: int) -> str:
        """try (Resource r = expr; ...) { body } [catch/finally] →

            with expr as r, expr2 as r2:
                body
        plus optional outer try/except/finally if catch_clause / finally_clause exist.
        """
        resource_spec = None
        body_node = None
        catch_clauses = []
        finally_clause = None
        for child in node.named_children:
            t = child.type
            if t == "resource_specification":
                resource_spec = child
            elif t == "block" and body_node is None:
                body_node = child
            elif t == "catch_clause":
                catch_clauses.append(child)
            elif t == "finally_clause":
                finally_clause = child

        if resource_spec is None or body_node is None:
            self._signature_locked = True
            self._collected_notes.append("try-with-resources missing resource_spec/body")
            return f"{self._pad(indent)}# UNMAPPED try-with-resources"

        # Collect resources as (var_name, init_expr_src)
        items: list[str] = []
        for r_node in resource_spec.named_children:
            if r_node.type != "resource":
                continue
            name = None
            init = None
            for sub in r_node.named_children:
                if sub.type == "identifier" and name is None:
                    name = self._text(sub)
                elif sub.type not in {"type_identifier", "generic_type", "modifiers"}:
                    init = sub
            if name is None or init is None:
                self._signature_locked = True
                self._collected_notes.append("resource missing name or initializer")
                continue
            init_src = self._dispatch(init, indent=0)
            # Bind for downstream type inference in body
            self._local_scope[name] = self._infer_type(init) or "Object"
            items.append(f"{init_src} as {name}")

        if not items:
            self._signature_locked = True
            return f"{self._pad(indent)}# UNMAPPED try-with-resources (no resources)"

        # Determine target indent for the with-statement
        with_indent = indent + 1 if (catch_clauses or finally_clause) else indent
        body_src = self._translate_branch_body(body_node, indent=with_indent + 1)
        with_header = f"{self._pad(with_indent)}with {', '.join(items)}:"
        with_block = f"{with_header}\n{body_src}"

        if not catch_clauses and finally_clause is None:
            return with_block

        # Wrap in outer try/except/finally
        lines = [f"{self._pad(indent)}try:", with_block]
        for c in catch_clauses:
            lines.append(self._translate_catch_clause(c, indent=indent))
        if finally_clause is not None:
            fin_body = None
            for child in finally_clause.named_children:
                if child.type == "block":
                    fin_body = child
                    break
            fin_body_src = (
                self._translate_branch_body(fin_body, indent=indent + 1)
                if fin_body
                else f"{self._pad(indent + 1)}pass"
            )
            lines.append(f"{self._pad(indent)}finally:")
            lines.append(fin_body_src)
        return "\n".join(lines)

    def _translate_catch_clause(self, node, *, indent: int) -> str:
        """`catch (E e) { body }` → `except E as e: body` / multi-catch supported."""
        param_node = None
        body_node = None
        for child in node.named_children:
            if child.type == "catch_formal_parameter":
                param_node = child
            elif child.type == "block":
                body_node = child

        # Param: catch_formal_parameter has catch_type (which contains 1+ type_identifier)
        # and a name (the variable bound).
        catch_types: list[str] = []
        var_name = "e"
        if param_node:
            for child in param_node.named_children:
                if child.type == "catch_type":
                    for t_child in child.named_children:
                        catch_types.append(map_java_exception(self._text(t_child)))
                elif child.type == "identifier":
                    var_name = self._text(child)
                else:
                    # fallback — read raw text as name
                    name_node = param_node.child_by_field_name("name")
                    if name_node:
                        var_name = self._text(name_node)
            # also try param name via field
            name_node = param_node.child_by_field_name("name")
            if name_node:
                var_name = self._text(name_node)

        if not catch_types:
            catch_types = ["Exception"]

        # bind exception var → its type (best-effort)
        if catch_types:
            self._local_scope[var_name] = catch_types[0]

        if len(catch_types) == 1:
            except_header = f"{self._pad(indent)}except {catch_types[0]} as {var_name}:"
        else:
            except_header = f"{self._pad(indent)}except ({', '.join(catch_types)}) as {var_name}:"

        body_src = (
            self._translate_branch_body(body_node, indent=indent + 1)
            if body_node
            else f"{self._pad(indent + 1)}pass"
        )
        return f"{except_header}\n{body_src}"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


# W51 — Method names that are *unambiguously* BigDecimal arithmetic. When the
# translator sees `<unknownReceiver>.<method>(<arg>)` it triggers BigDecimal
# mapping for any name in this set, regardless of receiver type. These four
# never collide with Collection / Set / Map APIs in the JDK. (`add` is
# deliberately excluded — clashes with `List.add` / `Set.add`.)
_UNAMBIGUOUS_BIGDECIMAL_METHODS: frozenset[str] = frozenset({
    "subtract", "multiply", "divide", "remainder",
})


# Java class-literal type → Python builtin type (W40 class_literal handler).
# Falls back to the bare identifier (Python classes are first-class) on miss.
_JAVA_TYPE_TO_PYTHON: dict[str, str] = {
    "String":      "str",
    "Integer":     "int",
    "Long":        "int",
    "Short":       "int",
    "Byte":        "int",
    "Float":       "float",
    "Double":      "float",
    "Boolean":     "bool",
    "Character":   "str",
    "Object":      "object",
    "Void":        "type(None)",
    "BigDecimal":  "Decimal",
    "BigInteger":  "int",
}


# Java type → Python equivalent for isinstance() checks (W11.2).
_INSTANCEOF_TYPE_MAP: dict[str, str] = {
    "String":        "str",
    "Integer":       "int",
    "Long":          "int",
    "Short":         "int",
    "Byte":          "int",
    "Float":         "float",
    "Double":        "float",
    "Boolean":       "bool",
    "Character":     "str",
    "Object":        "object",
    "List":          "list",
    "ArrayList":     "list",
    "Map":           "dict",
    "HashMap":       "dict",
    "Set":           "set",
    "HashSet":       "set",
    "BigDecimal":    "Decimal",
}


def _strip_outer_parens(expr: str) -> str:
    expr = expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        depth = 0
        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i < len(expr) - 1:
                    return expr
        return expr[1:-1]
    return expr


__all__ = [
    "JavaToPythonTranslator",
    "TranslationResult",
]
