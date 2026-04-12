"""Core mapping operations: CRUD, gap detection, inheritance resolution."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.mapping.mapping_models import (
    Mapping,
    MappingFile,
    MappingGap,
    MappingStatus,
)
from backend.modeling.mapping.yaml_store import load_mapping_yaml, save_mapping_yaml

logger = logging.getLogger(__name__)


class MappingService:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def load_yaml(self, path: Path) -> MappingFile:
        return load_mapping_yaml(path)

    def save_yaml(self, path: Path, mf: MappingFile) -> None:
        save_mapping_yaml(path, mf)

    def add_mapping(self, mf: MappingFile, mapping: Mapping) -> MappingFile:
        existing = {m.code for m in mf.mappings}
        if mapping.code in existing:
            raise ValueError(f"{mapping.code} is already mapped")
        mf.mappings.append(mapping)
        return mf

    def remove_mapping(self, mf: MappingFile, code: str) -> MappingFile:
        mf.mappings = [m for m in mf.mappings if m.code != code]
        return mf

    def update_status(
        self,
        mf: MappingFile,
        code: str,
        status: MappingStatus,
        confirmed_by: str | None = None,
    ) -> MappingFile:
        for m in mf.mappings:
            if m.code == code:
                m.status = status
                if status == MappingStatus.CONFIRMED and confirmed_by:
                    m.confirmed_by = confirmed_by
                    m.confirmed_at = datetime.now()
                return mf
        raise ValueError(f"Mapping not found: {code}")

    def find_gaps(self, mf: MappingFile, repo_id: str) -> list[MappingGap]:
        code_entities = self._neo4j.query(
            "MATCH (n:CodeEntity {repo_id: $repo_id}) WHERE n.kind IN ['class', 'interface'] "
            "RETURN n.qualified_name as qualified_name, n.kind as kind, n.file_path as file_path",
            {"repo_id": repo_id},
        )
        gaps = []
        for entity in code_entities:
            qn = entity["qualified_name"]
            if self.resolve(mf, qn) is None:
                gaps.append(
                    MappingGap(
                        qualified_name=qn,
                        kind=entity["kind"],
                        file_path=entity["file_path"],
                    )
                )
        return gaps

    def resolve(self, mf: MappingFile, qualified_name: str) -> str | None:
        """Resolve the domain mapping for a code entity, using inheritance."""
        # Direct match first
        for m in mf.mappings:
            if m.code == qualified_name:
                return m.domain
        # Walk up the package hierarchy
        parts = qualified_name.rsplit(".", 1)
        while len(parts) == 2:
            parent = parts[0]
            for m in mf.mappings:
                if m.code == parent:
                    return m.domain
            parts = parent.rsplit(".", 1)
        return None

    def sync_to_neo4j(self, mf: MappingFile) -> None:
        self._neo4j.write(
            "MATCH (:CodeEntity {repo_id: $repo_id})-[r:MAPPED_TO]->(:DomainNode) DELETE r",
            {"repo_id": mf.repo_id},
        )
        for m in mf.mappings:
            self._neo4j.write(
                """
                MATCH (c:CodeEntity {qualified_name: $code, repo_id: $repo_id})
                MATCH (d:DomainNode {id: $domain})
                MERGE (c)-[r:MAPPED_TO]->(d)
                SET r.status = $status, r.owner = $owner, r.granularity = $granularity
                """,
                {
                    "code": m.code,
                    "repo_id": mf.repo_id,
                    "domain": m.domain,
                    "status": m.status.value,
                    "owner": m.owner,
                    "granularity": m.granularity.value,
                },
            )
