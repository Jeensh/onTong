import pytest
from unittest.mock import MagicMock

from backend.modeling.ontology.domain_models import DomainNode, DomainNodeKind
from backend.modeling.ontology.ontology_store import OntologyStore


class TestOntologyStore:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.store = OntologyStore(self.neo4j)

    def test_load_template_writes_nodes(self):
        self.store.load_template()
        assert self.neo4j.write.call_count > 0

    def test_add_node(self):
        node = DomainNode(
            kind=DomainNodeKind.PROCESS,
            id="SCOR/Plan/Custom",
            name="Custom Process",
            parent_id="SCOR/Plan",
        )
        self.store.add_node(node)
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "MERGE" in cypher
        assert "DomainNode" in cypher

    def test_remove_node(self):
        self.store.remove_node("SCOR/Plan/Custom")
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "DELETE" in cypher

    def test_get_tree_returns_list(self):
        self.neo4j.query.return_value = [
            {"id": "SCOR/Plan", "name": "Plan", "kind": "process", "parent_id": None}
        ]
        result = self.store.get_tree()
        assert len(result) == 1

    def test_get_children(self):
        self.neo4j.query.return_value = [
            {"id": "SCOR/Plan/DemandPlanning", "name": "Demand Planning"}
        ]
        result = self.store.get_children("SCOR/Plan")
        assert len(result) == 1
