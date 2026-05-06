"""OD-11-B4 : JavaParser — 16 entity 중 기본 7 (code) + 5 relation 커버.

Spring-specific (AUTOWIRES, MAPS_URL, INTERCEPTS, PUBLISHES, HANDLES, HTTP_ENDPOINT,
SPRING_BEAN, ASPECT, SCHEDULED_TASK, MSG_LISTENER, EVENT_TYPE) 는 B5 에서 별 analyzer 로 다룬다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import (
    CodeParser,
    EntityKinds,
    RelationKinds,
)


SAMPLE_JAVA = """\
package com.example.inventory;

import com.example.data.StockRepository;

public class SafetyStockCalculator {
    private final StockRepository repo;

    public SafetyStockCalculator(StockRepository repo) {
        this.repo = repo;
    }

    public double calculate(double avgDemand, double leadTime, double serviceLevel) {
        double zScore = getZScore(serviceLevel);
        double stdDev = repo.getDemandStdDev();
        return zScore * stdDev * Math.sqrt(leadTime);
    }

    private double getZScore(double level) {
        if (level >= 0.99) return 2.33;
        if (level >= 0.95) return 1.65;
        return 1.28;
    }
}
"""


SAMPLE_INTERFACE = """\
package com.example.shapes;

import com.example.base.Drawable;

public interface Resizable extends Drawable {
    void resize(int width, int height);
}
"""

SAMPLE_ENUM = """\
package com.example.shapes;

public enum ShapeType {
    CIRCLE, SQUARE, TRIANGLE;
}
"""

SAMPLE_INHERITANCE = """\
package com.example.shapes;

import com.example.base.BaseShape;

public class Circle extends BaseShape implements Resizable {
    private double radius;

    public Circle(double radius) {
        this.radius = radius;
    }

    public void resize(int width, int height) {}

    public double area() {
        return Math.PI * radius * radius;
    }
}
"""


# ---------------------------------------------------------------------------
# Protocol conformance & basic meta
# ---------------------------------------------------------------------------
class TestJavaParserProtocol:
    def setup_method(self) -> None:
        self.parser = JavaParser()

    def test_conforms_to_code_parser_protocol(self) -> None:
        assert isinstance(self.parser, CodeParser)

    def test_supported_extensions(self) -> None:
        assert ".java" in self.parser.supported_extensions()

    def test_language_name(self) -> None:
        assert self.parser.language_name() == "Java"


# ---------------------------------------------------------------------------
# 7 code entity kinds
# ---------------------------------------------------------------------------
class TestEntityExtraction:
    def setup_method(self) -> None:
        self.parser = JavaParser()

    def test_extracts_package(self) -> None:
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        pkgs = [e for e in result.entities if e.kind == EntityKinds.PACKAGE]
        assert len(pkgs) == 1
        assert pkgs[0].qualified_name == "com.example.inventory"

    def test_extracts_class(self) -> None:
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        classes = [e for e in result.entities if e.kind == EntityKinds.CLASS]
        assert len(classes) == 1
        assert classes[0].qualified_name == "com.example.inventory.SafetyStockCalculator"

    def test_extracts_interface(self) -> None:
        result = self.parser.parse_file(Path("Resizable.java"), SAMPLE_INTERFACE)
        ifs = [e for e in result.entities if e.kind == EntityKinds.INTERFACE]
        assert len(ifs) == 1
        assert ifs[0].qualified_name == "com.example.shapes.Resizable"

    def test_extracts_enum(self) -> None:
        result = self.parser.parse_file(Path("ShapeType.java"), SAMPLE_ENUM)
        enums = [e for e in result.entities if e.kind == EntityKinds.ENUM]
        assert len(enums) == 1
        assert enums[0].qualified_name == "com.example.shapes.ShapeType"

    def test_extracts_methods(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        methods = [e for e in result.entities if e.kind == EntityKinds.METHOD]
        names = {m.name for m in methods}
        assert {"calculate", "getZScore"}.issubset(names)

    def test_extracts_constructor(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        ctors = [e for e in result.entities if e.kind == EntityKinds.CONSTRUCTOR]
        assert len(ctors) == 1
        assert ctors[0].name == "SafetyStockCalculator"

    def test_extracts_field(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        fields = [e for e in result.entities if e.kind == EntityKinds.FIELD]
        assert any(f.name == "repo" for f in fields)

    def test_entity_line_numbers_are_1based(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        classes = [e for e in result.entities if e.kind == EntityKinds.CLASS]
        assert classes[0].line_start >= 1
        assert classes[0].line_end > classes[0].line_start


# ---------------------------------------------------------------------------
# Relations: CONTAINS / CALLS / EXTENDS / IMPLEMENTS / DEPENDS_ON
# ---------------------------------------------------------------------------
class TestRelationExtraction:
    def setup_method(self) -> None:
        self.parser = JavaParser()

    def test_contains_package_to_class(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        contains = [
            r for r in result.relations
            if r.kind == RelationKinds.CONTAINS
            and r.source == "com.example.inventory"
            and r.target == "com.example.inventory.SafetyStockCalculator"
        ]
        assert len(contains) == 1

    def test_contains_class_to_method(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        contains = [
            r for r in result.relations
            if r.kind == RelationKinds.CONTAINS
            and r.target.endswith(".calculate")
        ]
        assert len(contains) == 1

    def test_calls_resolves_unqualified_to_same_class(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        calls = [r for r in result.relations if r.kind == RelationKinds.CALLS]
        assert any(
            r.target == "com.example.inventory.SafetyStockCalculator.getZScore"
            for r in calls
        )

    def test_extends_class_to_superclass(self) -> None:
        result = self.parser.parse_file(Path("Circle.java"), SAMPLE_INHERITANCE)
        ext = [r for r in result.relations if r.kind == RelationKinds.EXTENDS]
        assert any(r.target == "com.example.base.BaseShape" for r in ext)

    def test_implements_class_to_interface(self) -> None:
        result = self.parser.parse_file(Path("Circle.java"), SAMPLE_INHERITANCE)
        impl = [r for r in result.relations if r.kind == RelationKinds.IMPLEMENTS]
        assert any(r.target == "com.example.shapes.Resizable" for r in impl)

    def test_interface_extends_other_interface(self) -> None:
        result = self.parser.parse_file(Path("Resizable.java"), SAMPLE_INTERFACE)
        ext = [r for r in result.relations if r.kind == RelationKinds.EXTENDS]
        assert any(r.target == "com.example.base.Drawable" for r in ext)

    def test_depends_on_via_import(self) -> None:
        result = self.parser.parse_file(Path("x.java"), SAMPLE_JAVA)
        deps = [r for r in result.relations if r.kind == RelationKinds.DEPENDS_ON]
        assert any(r.target == "com.example.data.StockRepository" for r in deps)


# ---------------------------------------------------------------------------
# Syntax error collection
# ---------------------------------------------------------------------------
def test_parse_collects_syntax_errors() -> None:
    bad = "package com.x; public class Foo { void m() { @@@ } }"
    result = JavaParser().parse_file(Path("Bad.java"), bad)
    assert result.errors, "tree-sitter should report at least one ERROR node"
