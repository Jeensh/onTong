import pytest
from pathlib import Path

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKind, RelationKind


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


class TestJavaParser:
    def setup_method(self):
        self.parser = JavaParser()

    def test_supported_extensions(self):
        assert ".java" in self.parser.supported_extensions()

    def test_language_name(self):
        assert self.parser.language_name() == "Java"

    def test_parse_extracts_package(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        packages = [e for e in result.entities if e.kind == EntityKind.PACKAGE]
        assert len(packages) == 1
        assert packages[0].qualified_name == "com.example.inventory"

    def test_parse_extracts_class(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        classes = [e for e in result.entities if e.kind == EntityKind.CLASS]
        assert len(classes) == 1
        assert classes[0].qualified_name == "com.example.inventory.SafetyStockCalculator"
        assert "public" in classes[0].modifiers

    def test_parse_extracts_methods(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        methods = [e for e in result.entities if e.kind == EntityKind.METHOD]
        names = {m.name for m in methods}
        assert "calculate" in names
        assert "getZScore" in names

    def test_parse_extracts_field(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        fields = [e for e in result.entities if e.kind == EntityKind.FIELD]
        assert len(fields) == 1
        assert fields[0].name == "repo"

    def test_parse_extracts_contains_relations(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        contains = [r for r in result.relations if r.kind == RelationKind.CONTAINS]
        # package->class, class->methods, class->field, class->constructor
        assert len(contains) >= 4

    def test_parse_extracts_depends_on(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        deps = [r for r in result.relations if r.kind == RelationKind.DEPENDS_ON]
        targets = {d.target for d in deps}
        assert "com.example.data.StockRepository" in targets

    def test_parse_extracts_calls(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        calls = [r for r in result.relations if r.kind == RelationKind.CALLS]
        call_names = {c.target.split(".")[-1] for c in calls}
        assert "getZScore" in call_names

    def test_no_errors_on_valid_java(self):
        result = self.parser.parse_file(
            Path("Test.java"),
            SAMPLE_JAVA,
        )
        assert result.errors == []

    def test_parse_extracts_interface(self):
        result = self.parser.parse_file(
            Path("src/com/example/shapes/Resizable.java"),
            SAMPLE_INTERFACE,
        )
        interfaces = [e for e in result.entities if e.kind == EntityKind.INTERFACE]
        assert len(interfaces) == 1
        assert interfaces[0].qualified_name == "com.example.shapes.Resizable"
        assert "public" in interfaces[0].modifiers

    def test_parse_extracts_enum(self):
        result = self.parser.parse_file(
            Path("src/com/example/shapes/ShapeType.java"),
            SAMPLE_ENUM,
        )
        enums = [e for e in result.entities if e.kind == EntityKind.ENUM]
        assert len(enums) == 1
        assert enums[0].qualified_name == "com.example.shapes.ShapeType"

    def test_parse_extracts_constructor(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        constructors = [e for e in result.entities if e.kind == EntityKind.CONSTRUCTOR]
        assert len(constructors) == 1
        assert constructors[0].name == "SafetyStockCalculator"

    def test_parse_extracts_extends(self):
        # Test class EXTENDS
        result = self.parser.parse_file(
            Path("src/com/example/shapes/Circle.java"),
            SAMPLE_INHERITANCE,
        )
        extends = [r for r in result.relations if r.kind == RelationKind.EXTENDS]
        assert len(extends) == 1
        assert extends[0].source == "com.example.shapes.Circle"
        assert extends[0].target == "com.example.base.BaseShape"

        # Test interface EXTENDS
        result2 = self.parser.parse_file(
            Path("src/com/example/shapes/Resizable.java"),
            SAMPLE_INTERFACE,
        )
        extends2 = [r for r in result2.relations if r.kind == RelationKind.EXTENDS]
        assert len(extends2) == 1
        assert extends2[0].source == "com.example.shapes.Resizable"
        assert extends2[0].target == "com.example.base.Drawable"

    def test_parse_extracts_implements(self):
        result = self.parser.parse_file(
            Path("src/com/example/shapes/Circle.java"),
            SAMPLE_INHERITANCE,
        )
        implements = [r for r in result.relations if r.kind == RelationKind.IMPLEMENTS]
        assert len(implements) == 1
        assert implements[0].source == "com.example.shapes.Circle"
        assert implements[0].target == "com.example.shapes.Resizable"
