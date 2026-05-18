"""Per-method symbol scope for static type tracking.

Walks a method's params, local declarations, for-each loop variables,
try-with-resources resources, catch parameters, and Java 16+ instanceof
pattern variables, producing `name → declared_type_text` (raw Java text,
generics preserved). Used by `java_parser._extract_calls` to resolve the
static type of a method invocation's receiver.

Generic erasure (e.g. `List<Order>` vs `List`) is the caller's concern;
this module preserves the raw text so callers can decide whether to strip.
"""
from __future__ import annotations

from typing import Any


def build_method_scope(method_node: Any) -> dict[str, str]:
    """Return `dict[var_name, declared_type_text]` for one method.

    Captures (in order, with later writers shadowing earlier ones):
      1. Formal parameters
      2. Local variable declarations (any depth in the body)
      3. Enhanced-for loop variables (`for (X x : list)`)
      4. try-with-resources resource bindings
      5. catch_formal_parameter bindings (multi-type catch yields the first
         type, mirroring Java semantics for chained handlers)
      6. Java 16+ pattern instanceof variables (`x instanceof T t`)

    Block scoping is NOT enforced — a `for` body's local that shadows an
    outer local will simply overwrite the entry. In practice this is rare
    in production Java and matches what `_normalize_caller_fqns` already
    does for overload resolution (line-distance pick).
    """
    scope: dict[str, str] = {}

    # 1. Params
    params_node = method_node.child_by_field_name("parameters")
    if params_node is not None:
        for p in params_node.children:
            if p.type != "formal_parameter":
                continue
            name = _field_text(p, "name")
            type_text = _field_text(p, "type")
            if name and type_text:
                scope[name] = type_text

    # 2-6. Walk body
    body = method_node.child_by_field_name("body")
    if body is None:
        return scope

    for n in _walk(body):
        t = n.type
        if t == "local_variable_declaration":
            type_text = _field_text(n, "type")
            for ch in n.children:
                if ch.type == "variable_declarator":
                    name = _field_text(ch, "name")
                    if name and type_text:
                        scope[name] = type_text
        elif t == "enhanced_for_statement":
            name = _field_text(n, "name")
            type_text = _field_text(n, "type")
            if name and type_text:
                scope[name] = type_text
        elif t == "resource":
            # Child of resource_specification (inside try_with_resources_statement).
            # Resource node has children: [modifiers?] type_identifier name = value
            name = None
            type_text = None
            for ch in n.named_children:
                ct = ch.type
                if ct == "identifier" and name is None and type_text is not None:
                    name = ch.text.decode("utf-8", errors="ignore")
                elif ct in ("type_identifier", "scoped_type_identifier", "generic_type"):
                    type_text = ch.text.decode("utf-8", errors="ignore")
            if name and type_text:
                scope[name] = type_text
        elif t == "catch_formal_parameter":
            # children: [modifiers?] catch_type identifier
            name = _field_text(n, "name")
            # tree-sitter exposes 'catch_type' as the multi-type union; take
            # the first type_identifier inside it for our scope.
            type_text = None
            for ch in n.named_children:
                if ch.type == "catch_type":
                    for cc in ch.named_children:
                        if cc.type in ("type_identifier", "scoped_type_identifier", "generic_type"):
                            type_text = cc.text.decode("utf-8", errors="ignore")
                            break
                    break
            if name and type_text:
                scope[name] = type_text
        elif t == "instanceof_expression":
            # Java 16+: `x instanceof T t` produces three children:
            # [value, type, pattern_var(identifier)]. Bind pattern_var to type
            # for the lexical region — we apply method-flat scope, so later
            # references resolve correctly within the same method.
            children = n.named_children
            if len(children) >= 3 and children[2].type == "identifier":
                name = children[2].text.decode("utf-8", errors="ignore")
                type_text = children[1].text.decode("utf-8", errors="ignore")
                if name and type_text:
                    scope[name] = type_text

    return scope


def resolve_receiver(
    obj_node: Any,
    method_scope: dict[str, str],
    class_field_scope: dict[str, str],
    class_qname: str,
) -> tuple[str | None, str]:
    """Classify a method-invocation's receiver and return (type_text, kind).

    `type_text` is raw Java text (may contain generics); caller resolves to
    FQN via `_resolve_type`. Returns None when unresolvable at this stage.

    Kinds:
      - `implicit_this`   : no receiver node (unqualified call)
      - `this`            : explicit `this`
      - `name_param`      : bare identifier resolved from method params/locals
      - `name_field`      : bare identifier resolved from enclosing-class fields
      - `field_access`    : `this.X.method` or `X.Y.method` field walk
      - `chain`           : `a.b().c()` — receiver is itself a call; defer
      - `constructor`     : `new X(...)` chained call (`new X().y()`)
      - `static_class`    : upper-case identifier not in scope (likely class)
      - `unknown`         : couldn't classify
    """
    if obj_node is None:
        return class_qname, "implicit_this"

    t = obj_node.type
    if t == "this":
        return class_qname, "this"

    if t == "identifier":
        name = obj_node.text.decode("utf-8", errors="ignore")
        if name in method_scope:
            return method_scope[name], "name_param"
        if name in class_field_scope:
            return class_field_scope[name], "name_field"
        # Upper-case bare identifier → likely a static class reference
        # (e.g. `String.valueOf` / `Objects.equals`). Leave for static_class
        # handling — the type text IS the class name.
        if name and name[0].isupper():
            return name, "static_class"
        return None, "unknown"

    if t == "field_access":
        # Forms: `this.field.method()`, `field.method()`, `X.Y.method()`
        obj_child = obj_node.child_by_field_name("object")
        field_child = obj_node.child_by_field_name("field")
        if field_child is not None:
            field_name = field_child.text.decode("utf-8", errors="ignore")
            # `this.field`
            if obj_child is not None and obj_child.type == "this":
                if field_name in class_field_scope:
                    return class_field_scope[field_name], "field_access"
            # `field.X.method` — first segment resolved from class field scope
            elif obj_child is None or obj_child.type == "identifier":
                first = (obj_child.text.decode("utf-8", errors="ignore")
                         if obj_child is not None else field_name)
                if first in class_field_scope:
                    # Multi-level walk not done — return first hop only
                    return class_field_scope[first], "field_access"
        return None, "field_access"

    if t == "method_invocation":
        return None, "chain"

    if t == "object_creation_expression":
        # `new X().method()`
        type_node = obj_node.child_by_field_name("type")
        if type_node is not None:
            return type_node.text.decode("utf-8", errors="ignore"), "constructor"
        return None, "constructor"

    return None, "unknown"


def build_class_field_scope(class_body_node: Any) -> dict[str, str]:
    """Return `dict[field_name, field_type_text]` for one class body."""
    scope: dict[str, str] = {}
    if class_body_node is None:
        return scope
    for child in class_body_node.children:
        if child.type != "field_declaration":
            continue
        type_text = _field_text(child, "type")
        if not type_text:
            continue
        for sub in child.children:
            if sub.type == "variable_declarator":
                name = _field_text(sub, "name")
                if name:
                    scope[name] = type_text
    return scope


# ---------------------------------------------------------------- internals

def _field_text(node: Any, field: str) -> str | None:
    if node is None:
        return None
    child = node.child_by_field_name(field)
    if child is None:
        return None
    return child.text.decode("utf-8", errors="ignore")


def _walk(node: Any):
    yield node
    for c in node.children:
        yield from _walk(c)


__all__ = (
    "build_method_scope",
    "build_class_field_scope",
    "resolve_receiver",
)
