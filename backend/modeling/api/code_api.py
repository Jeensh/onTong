"""API endpoints for code analysis operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/modeling/code", tags=["modeling-code"])

# Injected at init
_git_connector = None
_java_parser = None
_graph_writer = None


def init(git_connector, java_parser, graph_writer):
    global _git_connector, _java_parser, _graph_writer
    _git_connector = git_connector
    _java_parser = java_parser
    _graph_writer = graph_writer


class ParseRequest(BaseModel):
    repo_url: str
    repo_id: str


class ParseResponse(BaseModel):
    repo_id: str
    files_parsed: int
    entities_count: int
    relations_count: int


@router.post("/parse", response_model=ParseResponse)
async def parse_repo(req: ParseRequest):
    """Clone/pull a Java repo and parse into code graph."""
    repo_path = _git_connector.clone(req.repo_url, req.repo_id)
    java_files = _git_connector.list_files(req.repo_id, extension=".java")

    total_entities = 0
    total_relations = 0
    _graph_writer.clear_repo(req.repo_id)

    for file_path in java_files:
        content = _git_connector.read_file(req.repo_id, file_path)
        result = _java_parser.parse_file(repo_path / file_path, content)
        _graph_writer.write_parse_result(result, repo_id=req.repo_id)
        total_entities += len(result.entities)
        total_relations += len(result.relations)

    return ParseResponse(
        repo_id=req.repo_id,
        files_parsed=len(java_files),
        entities_count=total_entities,
        relations_count=total_relations,
    )


@router.get("/graph/{repo_id}")
async def get_code_graph(repo_id: str, kind: str | None = None):
    """Get code entities and relations for a repo."""
    from backend.modeling.infrastructure.neo4j_client import Neo4jClient
    neo4j: Neo4jClient = _graph_writer._neo4j

    where_clause = ""
    params = {"repo_id": repo_id}
    if kind:
        where_clause = " WHERE n.kind = $kind"
        params["kind"] = kind

    entities = neo4j.query(
        f"MATCH (n:CodeEntity {{repo_id: $repo_id}}){where_clause} "
        "RETURN n.qualified_name as id, n.name as name, n.kind as kind, "
        "n.file_path as file_path, n.parent as parent "
        "ORDER BY n.qualified_name",
        params,
    )
    return {"repo_id": repo_id, "entities": entities, "count": len(entities)}
