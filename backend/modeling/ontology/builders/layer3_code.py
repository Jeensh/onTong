"""Layer 3 — Code Ontology 빌더.

스펙은 jQAssistant Maven 플러그인 사용을 가정하지만, jQA 2.x는 자체 embedded
Neo4j store에만 결과를 저장하고 외부 Bolt URI를 무시한다(알려진 동작).
이를 우회하기 위해 ``tree-sitter-java``로 직접 Java 소스를 파싱하여
:Class, :Method, :Table 노드와 관계를 docker Neo4j에 직접 적재한다.
스펙 §5 정규화 규칙(:Class.id, :Method.id, :Class-[:CONTAINS]->:Method)을
그대로 따른다.

직접 실행: ``python -m backend.modeling.ontology.builders.layer3_code``
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import tree_sitter_java
from tree_sitter import Language, Parser

from ..client import OntologyClient, close_client, get_client

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
JAVA_SRC = REPO_ROOT / "sample-repos" / "scm-demo" / "src" / "main" / "java"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TARGET_PACKAGE = "com.ontong.scm"

JAVA_LANG = Language(tree_sitter_java.language())


@dataclass
class JavaMethod:
    name: str
    return_type: str
    visibility: str  # public/private/protected/package


@dataclass
class JavaClass:
    fqn: str
    name: str
    package: str
    file: str
    kind: str  # class | interface | enum | record
    methods: list[JavaMethod]


def _text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8")


def _find_child(node, type_name: str):
    for c in node.children:
        if c.type == type_name:
            return c
    return None


def _parse_modifiers(modifiers_node, src: bytes) -> str:
    if modifiers_node is None:
        return "package"
    for c in modifiers_node.children:
        t = _text(c, src)
        if t in ("public", "private", "protected"):
            return t
    return "package"


def _extract_methods(class_body_node, src: bytes) -> list[JavaMethod]:
    methods: list[JavaMethod] = []
    for c in class_body_node.children:
        if c.type != "method_declaration":
            continue
        name = ""
        return_type = ""
        modifiers_node = _find_child(c, "modifiers")
        for child in c.children:
            if child.type == "identifier":
                name = _text(child, src)
            elif child.type in (
                "type_identifier",
                "void_type",
                "integral_type",
                "floating_point_type",
                "boolean_type",
                "generic_type",
                "array_type",
                "scoped_type_identifier",
            ) and not return_type:
                return_type = _text(child, src)
        methods.append(
            JavaMethod(
                name=name,
                return_type=return_type or "void",
                visibility=_parse_modifiers(modifiers_node, src),
            )
        )
    return methods


def parse_java_file(path: Path) -> list[JavaClass]:
    """단일 Java 파일에서 클래스 + 메서드 추출."""
    parser = Parser(JAVA_LANG)
    src = path.read_bytes()
    tree = parser.parse(src)
    root = tree.root_node

    package = ""
    for c in root.children:
        if c.type == "package_declaration":
            for cc in c.children:
                if cc.type == "scoped_identifier" or cc.type == "identifier":
                    package = _text(cc, src)
            break

    classes: list[JavaClass] = []

    def walk(node):
        kind_map = {
            "class_declaration": "class",
            "interface_declaration": "interface",
            "enum_declaration": "enum",
            "record_declaration": "record",
        }
        if node.type in kind_map:
            name_node = _find_child(node, "identifier")
            body_node = _find_child(node, "class_body") or _find_child(
                node, "interface_body"
            ) or _find_child(node, "enum_body") or _find_child(node, "record_body")
            if name_node is not None:
                name = _text(name_node, src)
                methods = _extract_methods(body_node, src) if body_node else []
                fqn = f"{package}.{name}" if package else name
                classes.append(
                    JavaClass(
                        fqn=fqn,
                        name=name,
                        package=package,
                        file=str(path.relative_to(REPO_ROOT)),
                        kind=kind_map[node.type],
                        methods=methods,
                    )
                )
        for child in node.children:
            walk(child)

    walk(root)
    return classes


def collect_classes(src_root: Path = JAVA_SRC) -> list[JavaClass]:
    """src_root 하위 모든 .java 파일을 스캔."""
    classes: list[JavaClass] = []
    for path in sorted(src_root.rglob("*.java")):
        try:
            classes.extend(parse_java_file(path))
        except Exception as exc:  # noqa: BLE001 — 단일 파일 실패가 전체 빌드를 막지 않도록
            logger.warning("Failed to parse %s: %s", path, exc)
    return classes


def ensure_constraints(client: OntologyClient) -> None:
    statements = [
        "CREATE CONSTRAINT class_id_unique IF NOT EXISTS "
        "FOR (c:Class) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT class_fqn_unique IF NOT EXISTS "
        "FOR (c:Class) REQUIRE c.fqn IS UNIQUE",
        "CREATE CONSTRAINT method_id_unique IF NOT EXISTS "
        "FOR (m:Method) REQUIRE m.id IS UNIQUE",
        "CREATE CONSTRAINT table_id_unique IF NOT EXISTS "
        "FOR (t:Table) REQUIRE t.id IS UNIQUE",
        "CREATE CONSTRAINT table_name_unique IF NOT EXISTS "
        "FOR (t:Table) REQUIRE t.name IS UNIQUE",
    ]
    for cypher in statements:
        client.write(cypher)


def clear_layer(client: OntologyClient) -> None:
    """Layer 3 노드만 삭제. Layer 1, 2 보존."""
    for label in ("Method", "Class", "Table"):
        client.write(f"MATCH (n:{label}) DETACH DELETE n")
    logger.info("Layer 3 cleared")


def upsert_classes_and_methods(
    client: OntologyClient, classes: list[JavaClass]
) -> tuple[int, int]:
    """:Class, :Method 노드 + (:Class)-[:CONTAINS]->(:Method)."""
    class_cypher = (
        "MERGE (c:Class {id: $id}) "
        "SET c.fqn = $fqn, "
        "    c.name = $name, "
        "    c.package = $package, "
        "    c.file = $file, "
        "    c.kind = $kind"
    )
    method_cypher = (
        "MERGE (m:Method {id: $id}) "
        "SET m.name = $name, "
        "    m.return_type = $return_type, "
        "    m.visibility = $visibility "
        "WITH m "
        "MATCH (c:Class {id: $class_id}) "
        "MERGE (c)-[:CONTAINS]->(m)"
    )

    statements: list[tuple[str, dict]] = []
    method_count = 0
    for cls in classes:
        class_id = "cls_" + cls.fqn.lower().replace(".", "_")
        statements.append(
            (
                class_cypher,
                {
                    "id": class_id,
                    "fqn": cls.fqn,
                    "name": cls.name,
                    "package": cls.package,
                    "file": cls.file,
                    "kind": cls.kind,
                },
            )
        )
        for m in cls.methods:
            method_id = f"method_{cls.name.lower()}_{m.name.lower()}"
            statements.append(
                (
                    method_cypher,
                    {
                        "id": method_id,
                        "name": m.name,
                        "return_type": m.return_type,
                        "visibility": m.visibility,
                        "class_id": class_id,
                    },
                )
            )
            method_count += 1
    client.write_tx(statements)
    logger.info(
        "Upserted %d Class nodes + %d Method nodes (with CONTAINS)",
        len(classes),
        method_count,
    )
    return len(classes), method_count


def upsert_tables(client: OntologyClient, tables: list[dict]) -> None:
    """:Table 노드 + (:Table)-[:MAPS_TO_STANDARD]->(:Standard)."""
    table_cypher = (
        "MERGE (t:Table {id: $id}) "
        "SET t.name = $name, "
        "    t.schema_name = $schema_name"
    )
    map_cypher = (
        "MATCH (t:Table {id: $table_id}) "
        "WITH t "
        "MATCH (s:Standard {code: $code}) "
        "MERGE (t)-[:MAPS_TO_STANDARD]->(s)"
    )
    statements: list[tuple[str, dict]] = []
    for tbl in tables:
        statements.append(
            (
                table_cypher,
                {
                    "id": tbl["id"],
                    "name": tbl["name"],
                    "schema_name": tbl["schema"],
                },
            )
        )
        statements.append(
            (
                map_cypher,
                {"table_id": tbl["id"], "code": tbl["maps_to_standard"]},
            )
        )
    client.write_tx(statements)
    logger.info(
        "Upserted %d Table nodes (with MAPS_TO_STANDARD)", len(tables)
    )


def build(client: OntologyClient | None = None) -> dict[str, int]:
    own_client = client is None
    client = client or get_client()
    try:
        with (DATA_DIR / "tables.json").open(encoding="utf-8") as f:
            tables = json.load(f)["tables"]

        ensure_constraints(client)
        clear_layer(client)

        classes = collect_classes()
        ontong_classes = [c for c in classes if c.fqn.startswith(TARGET_PACKAGE)]
        cls_count, method_count = upsert_classes_and_methods(client, ontong_classes)
        upsert_tables(client, tables)

        counts = {
            "classes": cls_count,
            "methods": method_count,
            "tables": len(tables),
        }
        logger.info("Layer 3 build complete: %s", counts)
        return counts
    finally:
        if own_client:
            close_client()


def _verify(client: OntologyClient) -> None:
    """검증 쿼리 5 + 추가 무결성 체크."""
    print("\n=== 검증 쿼리 5: com.ontong.scm 패키지 클래스 수 ===")
    rows = client.query(
        "MATCH (c:Class) WHERE c.fqn STARTS WITH 'com.ontong.scm' "
        "RETURN count(c) AS n"
    )
    n = rows[0]["n"]
    print(f"com.ontong.scm Class 개수 = {n} (expected ≥ 1)")
    assert n >= 1, f"Expected ≥1 class, got {n}"

    print("\n=== 추가 검증: Layer 3 노드/관계 카운트 ===")
    for label in ("Class", "Method", "Table"):
        rows = client.query(f"MATCH (n:{label}) RETURN count(n) AS n")
        print(f"{label} = {rows[0]['n']}")

    rows = client.query(
        "MATCH (:Class)-[r:CONTAINS]->(:Method) RETURN count(r) AS n"
    )
    print(f"CONTAINS = {rows[0]['n']}")
    rows = client.query(
        "MATCH (:Table)-[r:MAPS_TO_STANDARD]->(:Standard) RETURN count(r) AS n"
    )
    print(f"MAPS_TO_STANDARD = {rows[0]['n']} (expected 14)")
    assert rows[0]["n"] == 14

    print("\n=== Edging 매칭 확인 (Day 9 검증 쿼리 6 사전 점검) ===")
    rows = client.query(
        "MATCH (m:Method) WHERE m.name CONTAINS 'PrimaryWidth' OR m.name CONTAINS 'TargetWidth3Pass' "
        "RETURN m.name AS name ORDER BY m.name"
    )
    for r in rows:
        print(f"  Method: {r['name']}")

    print("\n✅ Layer 3 검증 통과")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    client = get_client()
    try:
        counts = build(client)
        print(f"\nBuild counts: {counts}")
        _verify(client)
    finally:
        close_client()


if __name__ == "__main__":
    main()
