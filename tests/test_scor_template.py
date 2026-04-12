import pytest

from backend.modeling.ontology.domain_models import DomainNodeKind
from backend.modeling.ontology.scor_template import load_scor_template


class TestSCORTemplate:
    def test_template_loads(self):
        ontology = load_scor_template()
        assert len(ontology.nodes) > 0

    def test_has_level_1_processes(self):
        ontology = load_scor_template()
        level1 = [
            n
            for n in ontology.nodes
            if n.id.count("/") == 1 and n.kind == DomainNodeKind.PROCESS
        ]
        names = {n.name for n in level1}
        assert "Plan" in names
        assert "Source" in names
        assert "Make" in names
        assert "Deliver" in names
        assert "Return" in names

    def test_has_level_2_processes(self):
        ontology = load_scor_template()
        plan_children = [n for n in ontology.nodes if n.parent_id == "SCOR/Plan"]
        assert len(plan_children) >= 3

    def test_has_isa95_make_breakdown(self):
        ontology = load_scor_template()
        make_descendants = [
            n for n in ontology.nodes if n.id.startswith("SCOR/Make/ISA95")
        ]
        assert len(make_descendants) >= 3

    def test_has_part_of_relations(self):
        ontology = load_scor_template()
        part_of = [r for r in ontology.relations if r.kind.value == "part_of"]
        assert len(part_of) > 0

    def test_all_nodes_have_unique_ids(self):
        ontology = load_scor_template()
        ids = [n.id for n in ontology.nodes]
        assert len(ids) == len(set(ids))
