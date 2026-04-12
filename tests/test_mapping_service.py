import pytest
from pathlib import Path
from unittest.mock import MagicMock

from backend.modeling.mapping.mapping_models import Mapping, MappingStatus, MappingFile
from backend.modeling.mapping.mapping_service import MappingService


class TestMappingService:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.service = MappingService(self.neo4j)

    def test_load_from_yaml(self, tmp_path):
        yaml_file = tmp_path / ".ontology" / "mapping.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text(
            'version: "1"\nrepo_id: test-repo\nmappings:\n'
            '  - code: "com.example.Foo"\n    domain: "SCOR/Plan"\n'
            '    status: confirmed\n    owner: kim\n'
        )
        mapping_file = self.service.load_yaml(yaml_file)
        assert len(mapping_file.mappings) == 1
        assert mapping_file.mappings[0].code == "com.example.Foo"
        assert mapping_file.mappings[0].status == MappingStatus.CONFIRMED

    def test_save_to_yaml(self, tmp_path):
        yaml_file = tmp_path / ".ontology" / "mapping.yaml"
        yaml_file.parent.mkdir(parents=True)
        mf = MappingFile(
            repo_id="test-repo",
            mappings=[
                Mapping(code="com.example.Bar", domain="SCOR/Source", owner="lee"),
            ],
        )
        self.service.save_yaml(yaml_file, mf)
        assert yaml_file.exists()
        content = yaml_file.read_text()
        assert "com.example.Bar" in content

    def test_add_mapping(self):
        mf = MappingFile(repo_id="test-repo", mappings=[])
        m = Mapping(code="com.example.Foo", domain="SCOR/Plan")
        result = self.service.add_mapping(mf, m)
        assert len(result.mappings) == 1

    def test_add_duplicate_mapping_raises(self):
        mf = MappingFile(
            repo_id="test-repo",
            mappings=[
                Mapping(code="com.example.Foo", domain="SCOR/Plan"),
            ],
        )
        m = Mapping(code="com.example.Foo", domain="SCOR/Source")
        with pytest.raises(ValueError, match="already mapped"):
            self.service.add_mapping(mf, m)

    def test_remove_mapping(self):
        mf = MappingFile(
            repo_id="test-repo",
            mappings=[
                Mapping(code="com.example.Foo", domain="SCOR/Plan"),
            ],
        )
        result = self.service.remove_mapping(mf, "com.example.Foo")
        assert len(result.mappings) == 0

    def test_find_gaps(self):
        self.neo4j.query.return_value = [
            {"qualified_name": "com.example.Foo", "kind": "class", "file_path": "Foo.java"},
            {"qualified_name": "com.example.Bar", "kind": "class", "file_path": "Bar.java"},
        ]
        mf = MappingFile(
            repo_id="test-repo",
            mappings=[
                Mapping(code="com.example.Foo", domain="SCOR/Plan"),
            ],
        )
        gaps = self.service.find_gaps(mf, "test-repo")
        assert len(gaps) == 1
        assert gaps[0].qualified_name == "com.example.Bar"

    def test_update_status(self):
        mf = MappingFile(
            repo_id="test-repo",
            mappings=[
                Mapping(
                    code="com.example.Foo",
                    domain="SCOR/Plan",
                    status=MappingStatus.DRAFT,
                ),
            ],
        )
        result = self.service.update_status(mf, "com.example.Foo", MappingStatus.REVIEW)
        assert result.mappings[0].status == MappingStatus.REVIEW

    def test_resolve_mapping_with_inheritance(self):
        mf = MappingFile(
            repo_id="test-repo",
            mappings=[
                Mapping(
                    code="com.example.inventory",
                    domain="SCOR/Plan/InventoryPlanning",
                    granularity="package",
                ),
            ],
        )
        domain = self.service.resolve(mf, "com.example.inventory.SafetyStockCalc")
        assert domain == "SCOR/Plan/InventoryPlanning"

    def test_resolve_with_override(self):
        mf = MappingFile(
            repo_id="test-repo",
            mappings=[
                Mapping(
                    code="com.example.inventory",
                    domain="SCOR/Plan/InventoryPlanning",
                    granularity="package",
                ),
                Mapping(
                    code="com.example.inventory.DemandForecaster",
                    domain="SCOR/Plan/DemandPlanning",
                    granularity="class",
                ),
            ],
        )
        domain = self.service.resolve(mf, "com.example.inventory.DemandForecaster")
        assert domain == "SCOR/Plan/DemandPlanning"
