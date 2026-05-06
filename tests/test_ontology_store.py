"""Tests for backend/modeling/ontology/ontology_store.py (OntNode-backed)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.modeling.ontology.ontology_store import OntologyStore


class TestOntologyStore:
    def setup_method(self) -> None:
        self.neo4j = MagicMock()
        self.store = OntologyStore(self.neo4j)

    @pytest.mark.skip(
        reason="OD-7/8 era yaml template removed in 2026-04-25 cleanup; OD-11 abandons ontology-first"
    )
    def test_load_template_persists_scor_isa95(self) -> None:
        count = self.store.load_template()
        # 26 processes + 7 entities + 5 roles = 38 node upserts.
        assert count == 38
        assert self.neo4j.write.call_count > 0
        cyphers = [call.args[0] for call in self.neo4j.write.call_args_list]
        assert any("OntNode" in c for c in cyphers)
        assert any(":PART_OF" in c for c in cyphers)
        assert any(":USES" in c for c in cyphers)
        assert any(":PRODUCES" in c for c in cyphers)
        assert any(":RESPONSIBLE_FOR" in c for c in cyphers)

    def test_add_node_uses_ontnode_label(self) -> None:
        self.store.add_node(
            id="SCOR/Plan/Custom",
            name="Custom Process",
            kind="process",
            parent_id="SCOR/Plan",
            description="user-added",
        )
        cypher, params = self.neo4j.write.call_args[0]
        assert "OntNode" in cypher
        assert "MERGE" in cypher
        assert params["id"] == "SCOR/Plan/Custom"
        assert params["kind"] == "process"
        assert params["parent_id"] == "SCOR/Plan"

    def test_update_node_sets_only_provided_fields(self) -> None:
        self.store.update_node("SCOR/Plan", name="Plan (v2)")
        cypher, params = self.neo4j.write.call_args[0]
        assert "n.name = $name" in cypher
        assert "n.description" not in cypher
        assert params == {"id": "SCOR/Plan", "name": "Plan (v2)"}

    def test_update_node_noop_when_nothing_to_set(self) -> None:
        self.store.update_node("SCOR/Plan")
        self.neo4j.write.assert_not_called()

    def test_remove_node_detach_deletes(self) -> None:
        self.store.remove_node("SCOR/Plan/Custom")
        cypher, params = self.neo4j.write.call_args[0]
        assert "DETACH DELETE" in cypher
        assert "OntNode" in cypher
        assert params == {"id": "SCOR/Plan/Custom"}

    def test_get_tree_returns_list(self) -> None:
        self.neo4j.query.return_value = [
            {
                "id": "SCOR/Plan",
                "name": "Plan",
                "kind": "process",
                "parent_id": None,
                "description": "",
            }
        ]
        result = self.store.get_tree()
        assert len(result) == 1
        cypher = self.neo4j.query.call_args[0][0]
        assert "OntNode" in cypher

    def test_get_children(self) -> None:
        self.neo4j.query.return_value = [
            {
                "id": "SCOR/Plan/DemandPlanning",
                "name": "Demand Planning",
                "kind": "process",
                "description": "",
            }
        ]
        result = self.store.get_children("SCOR/Plan")
        assert len(result) == 1
        cypher, params = self.neo4j.query.call_args[0]
        assert "OntNode" in cypher
        assert params == {"parent_id": "SCOR/Plan"}

    def test_get_node_returns_single_or_none(self) -> None:
        self.neo4j.query.return_value = [
            {
                "id": "SCOR/Plan",
                "name": "Plan",
                "kind": "process",
                "parent_id": None,
                "description": "",
            }
        ]
        found = self.store.get_node("SCOR/Plan")
        assert found is not None
        assert found["id"] == "SCOR/Plan"

        self.neo4j.query.return_value = []
        assert self.store.get_node("missing") is None
