"""Integration test for Section 2 Modeling MVP full flow.

Tests the pipeline: parse Java -> ontology -> mapping -> impact analysis -> approval
Uses mocked Neo4j client for deterministic testing without infrastructure.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKind, RelationKind
from backend.modeling.ontology.scor_template import load_scor_template
from backend.modeling.ontology.domain_models import DomainNodeKind
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus
from backend.modeling.mapping.mapping_service import MappingService
from backend.modeling.query.query_engine import QueryEngine
from backend.modeling.query.query_models import ImpactQuery
from backend.modeling.change.change_detector import ChangeDetector, ChangeKind
from backend.modeling.infrastructure.git_connector import GitDiff
from backend.modeling.approval.approval_service import ApprovalService
from backend.modeling.approval.approval_models import ReviewStatus


class TestModelingE2EFlow:
    """Tests the complete Section 2 pipeline with mocked Neo4j."""

    def setup_method(self):
        self.neo4j = MagicMock()
        self.parser = JavaParser()

    def test_step1_parse_java_code(self):
        """Step 1: Parse Java code and verify entity/relation extraction."""
        sample = '''
        package com.example.inventory;
        import com.example.order.OrderService;
        public class SafetyStockCalc {
            private double threshold;
            public double calculate(double demand, double leadTime) {
                double zScore = getZScore(0.95);
                return zScore * demand * Math.sqrt(leadTime);
            }
            private double getZScore(double level) {
                return 1.65;
            }
        }
        '''
        result = self.parser.parse_file(Path("SafetyStockCalc.java"), sample)

        assert result.errors == []
        assert result.language == "Java"

        # Verify entities
        entity_kinds = {e.kind for e in result.entities}
        assert EntityKind.PACKAGE in entity_kinds
        assert EntityKind.CLASS in entity_kinds
        assert EntityKind.METHOD in entity_kinds
        assert EntityKind.FIELD in entity_kinds

        # Verify relations
        rel_kinds = {r.kind for r in result.relations}
        assert RelationKind.CONTAINS in rel_kinds
        assert RelationKind.DEPENDS_ON in rel_kinds
        assert RelationKind.CALLS in rel_kinds

    def test_step2_load_scor_ontology(self):
        """Step 2: Load SCOR template and verify completeness."""
        ontology = load_scor_template()

        assert len(ontology.nodes) >= 30

        # Verify all SCOR L1 processes
        l1_names = {
            n.name
            for n in ontology.nodes
            if n.id.count("/") == 1 and n.kind == DomainNodeKind.PROCESS
        }
        assert l1_names == {"Plan", "Source", "Make", "Deliver", "Return"}

        # Verify ISA-95 under Make
        isa95 = [n for n in ontology.nodes if "ISA95" in n.id]
        assert len(isa95) >= 3

        # Verify entities exist
        entities = [n for n in ontology.nodes if n.kind == DomainNodeKind.ENTITY]
        assert len(entities) >= 5

        # Verify all node IDs are unique
        ids = [n.id for n in ontology.nodes]
        assert len(ids) == len(set(ids))

    def test_step3_mapping_crud_and_inheritance(self, tmp_path):
        """Step 3: Create mappings, test YAML persistence and inheritance."""
        svc = MappingService(self.neo4j)

        # Create mapping file
        mf = MappingFile(repo_id="test-repo", mappings=[])

        # Add mappings
        mf = svc.add_mapping(mf, Mapping(
            code="com.example.inventory",
            domain="SCOR/Plan/InventoryPlanning",
            granularity="package",
            owner="kim",
        ))
        mf = svc.add_mapping(mf, Mapping(
            code="com.example.order.OrderService",
            domain="SCOR/Deliver/OrderManagement",
            owner="lee",
        ))

        assert len(mf.mappings) == 2

        # Test inheritance: class under mapped package resolves
        domain = svc.resolve(mf, "com.example.inventory.SafetyStockCalc")
        assert domain == "SCOR/Plan/InventoryPlanning"

        # Test direct match overrides inheritance
        mf = svc.add_mapping(mf, Mapping(
            code="com.example.inventory.DemandForecaster",
            domain="SCOR/Plan/DemandPlanning",
        ))
        domain = svc.resolve(mf, "com.example.inventory.DemandForecaster")
        assert domain == "SCOR/Plan/DemandPlanning"

        # Test YAML round-trip
        yaml_path = tmp_path / ".ontology" / "mapping.yaml"
        svc.save_yaml(yaml_path, mf)
        loaded = svc.load_yaml(yaml_path)
        assert len(loaded.mappings) == 3
        assert loaded.mappings[0].code == "com.example.inventory"

    def test_step4_impact_analysis(self):
        """Step 4: Run impact analysis with mocked graph."""
        engine = QueryEngine(self.neo4j)

        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.inventory.SafetyStockCalc",
                    domain="SCOR/Plan/InventoryPlanning",
                    status=MappingStatus.CONFIRMED, owner="kim"),
            Mapping(code="com.example.order.OrderService",
                    domain="SCOR/Deliver/OrderManagement",
                    status=MappingStatus.CONFIRMED, owner="lee"),
        ])

        # Mock BFS: OrderService depends on SafetyStockCalc
        self.neo4j.query.side_effect = [
            [{"qn": "com.example.order.OrderService", "depth": 1}],  # BFS result
            [{"name": "Order Management"}],  # domain name lookup
        ]

        query = ImpactQuery(term="SafetyStockCalc", repo_id="test-repo")
        result = engine.analyze(query, mf)

        assert result.resolved is True
        assert result.source_code_entity == "com.example.inventory.SafetyStockCalc"
        assert len(result.affected_processes) >= 1

        affected_domains = {p.domain_id for p in result.affected_processes}
        assert "SCOR/Deliver/OrderManagement" in affected_domains

    def test_step5_change_detection(self):
        """Step 5: Detect impact of code changes on mappings."""
        detector = ChangeDetector(self.neo4j)

        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Foo", domain="SCOR/Plan", owner="kim",
                    status=MappingStatus.CONFIRMED),
        ])

        diff = GitDiff(modified=["src/Foo.java"], added=["src/Bar.java"], deleted=[])
        self.neo4j.query.side_effect = [
            [{"qualified_name": "com.example.Foo"}],   # entities in modified file
            [{"qualified_name": "com.example.Bar"}],    # entities in added file
        ]

        impacts = detector.classify(diff, mf, "test-repo")

        review = [i for i in impacts if i.kind == ChangeKind.REVIEW]
        assert len(review) == 1
        assert review[0].owner == "kim"

        unmapped = [i for i in impacts if i.kind == ChangeKind.UNMAPPED]
        assert len(unmapped) == 1

    def test_step6_approval_workflow(self):
        """Step 6: Complete approval workflow."""
        svc = ApprovalService()

        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Foo", domain="SCOR/Plan",
                    status=MappingStatus.REVIEW, owner="kim"),
        ])

        # Create review
        review = svc.create_review("com.example.Foo", "SCOR/Plan", "test-repo", "kim")
        assert review.status == ReviewStatus.PENDING

        # Approve
        review, mf = svc.approve(review.id, "lee-biz", mf)
        assert review.status == ReviewStatus.APPROVED
        assert mf.mappings[0].status == MappingStatus.CONFIRMED
        assert mf.mappings[0].confirmed_by == "lee-biz"

    def test_full_pipeline_summary(self, tmp_path):
        """Summary test: verify all components can work together."""
        # 1. Parse
        result = self.parser.parse_file(Path("Test.java"), '''
        package com.test;
        public class Calculator {
            public int add(int a, int b) { return a + b; }
        }
        ''')
        assert len(result.entities) >= 3  # package, class, method

        # 2. Ontology
        ontology = load_scor_template()
        assert len(ontology.nodes) >= 30

        # 3. Mapping
        svc = MappingService(self.neo4j)
        mf = MappingFile(repo_id="test", mappings=[])
        mf = svc.add_mapping(mf, Mapping(code="com.test.Calculator", domain="SCOR/Make/Manufacturing"))
        yaml_path = tmp_path / "mapping.yaml"
        svc.save_yaml(yaml_path, mf)
        loaded = svc.load_yaml(yaml_path)
        assert loaded.mappings[0].domain == "SCOR/Make/Manufacturing"

        # 4. Query (unresolved term)
        engine = QueryEngine(self.neo4j)
        result = engine.analyze(ImpactQuery(term="NonExistent", repo_id="test"), mf)
        assert result.resolved is False
