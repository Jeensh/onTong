"""OD-11-B6-3 : Spring NativeSqlAnalyzer.

Detect SQL call sites (Spring Data `@Query`, `EntityManager.createNativeQuery` /
`createQuery`, `JdbcTemplate.query/update/...`) and emit lineage edges
`READS_TABLE` / `WRITES_TABLE` with `columns`, `confidence`, `raw_sql`, `dialect`
attributes. DB_TABLE entity creation is deferred to B6-4 (repo-wide dedup).

Design:
  - `analyze()` directly emits relations (standalone pattern — B6-SPEC D7).
  - `enrich()` is a no-op (identity on inputs).
  - SQL parsing : `sqlglot.parse(sql, error_level="ignore")` (default dialect).
  - Multi-statement : only the first statement is processed; edges carry
    `multi_statement_warning = True`.
  - Dynamic SQL (non-string-literal first arg, e.g., concat / identifier) :
    emit a single `<dynamic>` marker edge with `confidence=0.3`.
  - Table names are lowercased on the edge `target`; `raw_sql` keeps the
    original string verbatim.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    RelationKinds,
)

_ENTITY_MANAGER_FQNS = frozenset(
    {
        "javax.persistence.EntityManager",
        "jakarta.persistence.EntityManager",
        "EntityManager",
    }
)
_JDBC_TEMPLATE_FQNS = frozenset(
    {
        "org.springframework.jdbc.core.JdbcTemplate",
        "JdbcTemplate",
    }
)

_JDBC_READ_METHODS = frozenset({"query", "queryForObject", "queryForList"})

# P30-3 — QueryDSL JPAQueryFactory pattern
_JPA_QUERY_FACTORY_FQNS = frozenset({
    "com.querydsl.jpa.impl.JPAQueryFactory",
    "JPAQueryFactory",
})
_QDSL_READ_METHODS = frozenset({"selectFrom", "select", "selectDistinct", "selectOne"})
_QDSL_WRITE_METHODS = frozenset({"update", "delete", "insert"})
_JDBC_WRITE_METHODS = frozenset({"update", "batchUpdate"})

_DIALECT_SQL = "sql"
_DIALECT_JPQL = "jpql"

_DYNAMIC = "<dynamic>"
_UNRESOLVED = "<unresolved>"


class NativeSqlAnalyzer:
    """`@Query` / `EntityManager` / `JdbcTemplate` SQL → READS_TABLE / WRITES_TABLE."""

    # -- Protocol entry : standalone analyze ------------------------------------

    def analyze(
        self,
        tree: object | None,
        content: bytes,
        file_path: str,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        if tree is None:
            return [], []
        root: Node = tree.root_node  # type: ignore[attr-defined]
        import_map = self._build_import_map(root)

        relations: list[CodeRelation] = []
        for child in root.children:
            if child.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                self._scan_type(
                    type_node=child,
                    pkg_name=pkg_name,
                    import_map=import_map,
                    parent_qname=None,
                    relations=relations,
                )
        return [], relations

    # -- enrich is no-op --------------------------------------------------------

    def enrich(
        self,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        tree: object | None,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        return entities, relations

    # -- type / method traversal -----------------------------------------------

    def _scan_type(
        self,
        type_node: Node,
        pkg_name: str | None,
        import_map: dict[str, str],
        parent_qname: str | None,
        relations: list[CodeRelation],
    ) -> None:
        name_node = type_node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        if parent_qname:
            class_qname = f"{parent_qname}.{class_name}"
        elif pkg_name:
            class_qname = f"{pkg_name}.{class_name}"
        else:
            class_qname = class_name

        body = type_node.child_by_field_name("body")
        if body is None:
            return

        field_types = self._build_field_types(body, import_map, pkg_name)

        for member in body.children:
            if member.type == "method_declaration":
                mname = member.child_by_field_name("name")
                if mname is None:
                    continue
                method_fqn = f"{class_qname}.{mname.text.decode()}"
                # @Query + @Modifying at method level
                self._emit_query_edges(member, method_fqn, relations)
                # Body scan: em/jdbc calls
                scope = self._build_scope_map(
                    member, field_types, import_map, pkg_name, class_qname
                )
                self._scan_body(member, method_fqn, scope, relations)
            elif member.type == "constructor_declaration":
                cname = member.child_by_field_name("name")
                if cname is None:
                    continue
                ctor_fqn = f"{class_qname}.{cname.text.decode()}"
                scope = self._build_scope_map(
                    member, field_types, import_map, pkg_name, class_qname
                )
                self._scan_body(member, ctor_fqn, scope, relations)
            elif member.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                self._scan_type(
                    type_node=member,
                    pkg_name=pkg_name,
                    import_map=import_map,
                    parent_qname=class_qname,
                    relations=relations,
                )

    # -- @Query / @Modifying handling ------------------------------------------

    def _emit_query_edges(
        self,
        method_node: Node,
        method_fqn: str,
        relations: list[CodeRelation],
    ) -> None:
        annotations = _collect_method_annotations(method_node)
        query_ann: Node | None = None
        for ann in annotations:
            if ann["name"] == "Query":
                query_ann = ann["node"]
                break
        if query_ann is None:
            return
        sql, is_native = _extract_query_attrs(query_ann)
        if not sql:
            return
        dialect = _DIALECT_SQL if is_native else _DIALECT_JPQL
        relations.extend(self._parse_sql_to_edges(method_fqn, sql, dialect))

    # -- body invocation scan --------------------------------------------------

    def _scan_body(
        self,
        member_node: Node,
        method_fqn: str,
        scope: dict[str, str],
        relations: list[CodeRelation],
    ) -> None:
        body = member_node.child_by_field_name("body")
        if body is None:
            return
        for n in _walk(body):
            if n.type != "method_invocation":
                continue
            relations.extend(self._classify_invocation(n, method_fqn, scope))

    def _classify_invocation(
        self,
        inv: Node,
        method_fqn: str,
        scope: dict[str, str],
    ) -> list[CodeRelation]:
        name_node = inv.child_by_field_name("name")
        obj_node = inv.child_by_field_name("object")
        args_node = inv.child_by_field_name("arguments")
        if name_node is None or args_node is None:
            return []
        method_name = name_node.text.decode()
        obj_type = _lookup_obj_type(obj_node, scope)

        if method_name == "createNativeQuery" and obj_type in _ENTITY_MANAGER_FQNS:
            return self._edges_from_first_arg(
                args_node, method_fqn, dialect=_DIALECT_SQL, force_kind=None,
            )
        if method_name == "createQuery" and obj_type in _ENTITY_MANAGER_FQNS:
            return self._edges_from_first_arg(
                args_node, method_fqn, dialect=_DIALECT_JPQL, force_kind=None,
            )
        if method_name in _JDBC_READ_METHODS and obj_type in _JDBC_TEMPLATE_FQNS:
            return self._edges_from_first_arg(
                args_node, method_fqn, dialect=_DIALECT_SQL, force_kind="read",
            )
        if method_name in _JDBC_WRITE_METHODS and obj_type in _JDBC_TEMPLATE_FQNS:
            return self._edges_from_first_arg(
                args_node, method_fqn, dialect=_DIALECT_SQL, force_kind="write",
            )
        # P30-3 — QueryDSL JPAQueryFactory pattern
        if obj_type in _JPA_QUERY_FACTORY_FQNS:
            if method_name in _QDSL_READ_METHODS:
                return self._edges_from_qdsl_arg(args_node, method_fqn, force_kind="read")
            if method_name in _QDSL_WRITE_METHODS:
                return self._edges_from_qdsl_arg(args_node, method_fqn, force_kind="write")
        return []

    # -- argument extraction + SQL parse ---------------------------------------

    def _edges_from_first_arg(
        self,
        args_node: Node,
        method_fqn: str,
        dialect: str,
        force_kind: str | None,
    ) -> list[CodeRelation]:
        arg_nodes = [c for c in args_node.children if c.type not in ("(", ",", ")")]
        if not arg_nodes:
            return []
        first = arg_nodes[0]
        if first.type == "string_literal":
            sql = _string_literal_text(first)
            return self._parse_sql_to_edges(method_fqn, sql, dialect, force_kind=force_kind)
        raw = first.text.decode()
        kind = RelationKinds.WRITES_TABLE if force_kind == "write" else RelationKinds.READS_TABLE
        return [
            CodeRelation(
                kind=kind,
                source=method_fqn,
                target=_DYNAMIC,
                attributes={
                    "columns": [_DYNAMIC],
                    "confidence": 0.3,
                    "raw_sql": raw,
                    "dialect": dialect,
                },
            )
        ]

    # -- P30-3 — QueryDSL --------------------------------------------------------

    def _edges_from_qdsl_arg(
        self,
        args_node: Node,
        method_fqn: str,
        force_kind: str,
    ) -> list[CodeRelation]:
        """QueryDSL JPAQueryFactory pattern : `queryFactory.selectFrom(QSlab.slab)`.

        Strategy:
          - Extract QClass entity name from first arg (Q-prefix strip → 'Slab').
          - Emit edge with target = entity name + dialect = 'jpql' so that
            cross_file_enricher's _resolve_jpql_to_table maps Slab → @Table(name).
          - confidence = 0.5 (predicates are dynamic, not parsed).
          - via = 'querydsl' attr for downstream lineage classification.
        """
        kind = (
            RelationKinds.WRITES_TABLE if force_kind == "write" else RelationKinds.READS_TABLE
        )
        arg_nodes = [c for c in args_node.children if c.type not in ("(", ",", ")")]
        raw = args_node.text.decode() if args_node is not None else ""
        if not arg_nodes:
            return []
        first = arg_nodes[0]
        entity_name = _infer_qclass_entity(first)
        if not entity_name:
            return [
                CodeRelation(
                    kind=kind,
                    source=method_fqn,
                    target=_DYNAMIC,
                    attributes={
                        "columns": [_DYNAMIC],
                        "confidence": 0.3,
                        "raw_sql": raw,
                        "dialect": "querydsl",
                        "via": "querydsl",
                    },
                )
            ]
        return [
            CodeRelation(
                kind=kind,
                source=method_fqn,
                target=entity_name,
                attributes={
                    "columns": [_DYNAMIC],
                    "confidence": 0.5,
                    "raw_sql": raw,
                    "dialect": _DIALECT_JPQL,
                    "via": "querydsl",
                    "dynamic_predicates": True,
                },
            )
        ]

    def _parse_sql_to_edges(
        self,
        method_fqn: str,
        sql: str,
        dialect: str,
        force_kind: str | None = None,
    ) -> list[CodeRelation]:
        if not sql.strip():
            return []
        try:
            statements = sqlglot.parse(sql, error_level="ignore")
        except Exception:
            return [_dynamic_edge(method_fqn, sql, dialect, force_kind)]
        statements = [s for s in statements if s is not None]
        if not statements:
            return [_dynamic_edge(method_fqn, sql, dialect, force_kind)]
        multi = len(statements) > 1
        stmt = statements[0]

        try:
            write_tables, read_tables = _split_tables(stmt)
            cols = _ordered_unique_columns(stmt)
        except Exception:
            return [_dynamic_edge(method_fqn, sql, dialect, force_kind)]

        if not write_tables and not read_tables:
            # Parsed but no tables (e.g., `SELECT 1`) — skip edge emission.
            return []

        base = {
            "columns": cols,
            "confidence": 1.0,
            "raw_sql": sql,
            "dialect": dialect,
        }
        if multi:
            base["multi_statement_warning"] = True

        out: list[CodeRelation] = []
        for t in write_tables:
            out.append(
                CodeRelation(
                    kind=RelationKinds.WRITES_TABLE,
                    source=method_fqn,
                    target=t.lower(),
                    attributes=dict(base),
                )
            )
        for t in read_tables:
            out.append(
                CodeRelation(
                    kind=RelationKinds.READS_TABLE,
                    source=method_fqn,
                    target=t.lower(),
                    attributes=dict(base),
                )
            )
        return out

    # -- import / scope helpers ------------------------------------------------

    @staticmethod
    def _build_import_map(root: Node) -> dict[str, str]:
        import_map: dict[str, str] = {}
        for child in root.children:
            if child.type != "import_declaration":
                continue
            text = child.text.decode().strip()
            if not text.startswith("import"):
                continue
            body = text[len("import") :].strip()
            if body.endswith(";"):
                body = body[:-1].strip()
            if body.startswith("static "):
                continue
            if body.endswith(".*"):
                continue
            if not body:
                continue
            simple = body.rsplit(".", 1)[-1]
            import_map[simple] = body
        return import_map

    def _build_field_types(
        self,
        class_body: Node,
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in class_body.children:
            if c.type != "field_declaration":
                continue
            type_node = c.child_by_field_name("type")
            if type_node is None:
                continue
            resolved = _resolve_type(type_node.text.decode(), import_map, pkg_name)
            for cc in c.children:
                if cc.type == "variable_declarator":
                    vname = cc.child_by_field_name("name")
                    if vname is not None:
                        out[vname.text.decode()] = resolved
        return out

    def _build_scope_map(
        self,
        member_node: Node,
        field_types: dict[str, str],
        import_map: dict[str, str],
        pkg_name: str | None,
        class_qname: str,
    ) -> dict[str, str]:
        scope: dict[str, str] = dict(field_types)
        scope["this"] = class_qname
        params = member_node.child_by_field_name("parameters")
        if params is not None:
            for p in params.children:
                if p.type != "formal_parameter":
                    continue
                ptype = p.child_by_field_name("type")
                pname = p.child_by_field_name("name")
                if ptype is None or pname is None:
                    continue
                scope[pname.text.decode()] = _resolve_type(
                    ptype.text.decode(), import_map, pkg_name
                )
        body = member_node.child_by_field_name("body")
        if body is not None:
            for n in _walk(body):
                if n.type == "local_variable_declaration":
                    ltype = n.child_by_field_name("type")
                    if ltype is None:
                        continue
                    resolved = _resolve_type(ltype.text.decode(), import_map, pkg_name)
                    for cc in n.children:
                        if cc.type == "variable_declarator":
                            vname = cc.child_by_field_name("name")
                            if vname is not None:
                                scope[vname.text.decode()] = resolved
        return scope


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------
def _split_tables(stmt: exp.Expression) -> tuple[list[str], list[str]]:
    """Return (write_tables, read_tables) based on statement root kind.

    Insert  : target = stmt.this (Table or Schema(Table, ...)), source tables
              come from stmt.expression (Select) if INSERT ... SELECT.
    Update / Delete : first Table is write target, any further tables (from
              sub-queries in WHERE, etc.) are reads.
    Other (Select / Union / CTE ...) : all tables are reads.
    """
    write: list[str] = []
    read: list[str] = []
    if isinstance(stmt, exp.Insert):
        target_name = _insert_target_name(stmt.this)
        if target_name:
            write.append(target_name)
        source_expr = stmt.expression
        if source_expr is not None:
            for t in source_expr.find_all(exp.Table):
                name = _table_name(t)
                if name and name != target_name and name not in read:
                    read.append(name)
    elif isinstance(stmt, (exp.Update, exp.Delete)):
        tables = list(stmt.find_all(exp.Table))
        for idx, t in enumerate(tables):
            name = _table_name(t)
            if not name:
                continue
            if idx == 0:
                if name not in write:
                    write.append(name)
            else:
                if name not in read:
                    read.append(name)
    else:
        for t in stmt.find_all(exp.Table):
            name = _table_name(t)
            if name and name not in read:
                read.append(name)
    return write, read


def _insert_target_name(target: exp.Expression | None) -> str | None:
    """INSERT target can be Table or Schema(Table, columns)."""
    if target is None:
        return None
    if isinstance(target, exp.Table):
        return _table_name(target)
    if isinstance(target, exp.Schema):
        inner = target.this
        if isinstance(inner, exp.Table):
            return _table_name(inner)
    return None


def _table_name(table_node: exp.Table) -> str | None:
    try:
        name = table_node.name
    except Exception:
        return None
    return name or None


def _ordered_unique_columns(stmt: exp.Expression) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for c in stmt.find_all(exp.Column):
        name = c.name if hasattr(c, "name") else None
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _dynamic_edge(
    method_fqn: str,
    raw: str,
    dialect: str,
    force_kind: str | None,
) -> CodeRelation:
    kind = RelationKinds.WRITES_TABLE if force_kind == "write" else RelationKinds.READS_TABLE
    return CodeRelation(
        kind=kind,
        source=method_fqn,
        target=_DYNAMIC,
        attributes={
            "columns": [_DYNAMIC],
            "confidence": 0.3,
            "raw_sql": raw,
            "dialect": dialect,
        },
    )


# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------
def _collect_method_annotations(method_node: Node) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for c in method_node.children:
        if c.type != "modifiers":
            continue
        for m in c.children:
            if m.type in ("annotation", "marker_annotation"):
                name = _annotation_name(m)
                if name:
                    out.append({"name": name, "node": m})
    return out


def _annotation_name(ann_node: Node) -> str | None:
    name_node = ann_node.child_by_field_name("name")
    if name_node is not None:
        return name_node.text.decode().rsplit(".", 1)[-1]
    for c in ann_node.children:
        if c.type == "identifier":
            return c.text.decode()
        if c.type == "scoped_identifier":
            return c.text.decode().rsplit(".", 1)[-1]
    return None


def _extract_query_attrs(ann_node: Node) -> tuple[str | None, bool]:
    """Return (sql, is_native) from `@Query(...)`."""
    args = ann_node.child_by_field_name("arguments")
    if args is None:
        for c in ann_node.children:
            if c.type == "annotation_argument_list":
                args = c
                break
    if args is None:
        return None, False

    sql: str | None = None
    is_native: bool = False
    for c in args.children:
        if c.type == "string_literal":
            # Positional (treated as `value`).
            sql = _string_literal_text(c)
        elif c.type == "element_value_pair":
            key: str | None = None
            val: object | None = None
            for pc in c.children:
                if pc.type == "identifier" and key is None:
                    key = pc.text.decode()
                elif pc.type == "string_literal":
                    val = _string_literal_text(pc)
                elif pc.type == "true":
                    val = True
                elif pc.type == "false":
                    val = False
            if key == "value" and isinstance(val, str):
                sql = val
            elif key == "nativeQuery" and isinstance(val, bool):
                is_native = val
    return sql, is_native


# ---------------------------------------------------------------------------
# Generic helpers (shared with BeanUtilsAnalyzer style)
# ---------------------------------------------------------------------------
def _resolve_type(simple: str, import_map: dict[str, str], pkg_name: str | None) -> str:
    if not simple:
        return _UNRESOLVED
    root = simple.split("<", 1)[0].rstrip("[]").strip()
    if not root:
        return _UNRESOLVED
    if root in import_map:
        return import_map[root]
    return root


def _lookup_obj_type(obj_node: Node | None, scope: dict[str, str]) -> str | None:
    if obj_node is None:
        return None
    if obj_node.type == "identifier":
        return scope.get(obj_node.text.decode())
    if obj_node.type == "this":
        return scope.get("this")
    if obj_node.type == "field_access":
        field_node = obj_node.child_by_field_name("field")
        if field_node is not None:
            return scope.get(field_node.text.decode())
    return None


def _infer_qclass_entity(node: Node) -> str | None:
    """QueryDSL Q-class → entity simple name. e.g. `QSlab.slab` → 'Slab'.

    Patterns supported:
      - field_access: `QFoo.foo` → 'Foo'
      - identifier: `QFoo` → 'Foo' (rare but legal)
    Returns None if not a Q-prefixed PascalCase identifier.
    """
    target_node: Node | None = None
    if node.type == "field_access":
        target_node = node.child_by_field_name("object")
    elif node.type == "identifier":
        target_node = node
    if target_node is None or target_node.type != "identifier":
        return None
    text = target_node.text.decode()
    if len(text) < 2 or text[0] != "Q":
        return None
    if not text[1].isupper():
        return None
    return text[1:]


def _string_literal_text(node: Node) -> str:
    for c in node.children:
        if c.type == "string_fragment":
            return c.text.decode()
    text = node.text.decode()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _walk(node: Node):
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


__all__ = ("NativeSqlAnalyzer",)
