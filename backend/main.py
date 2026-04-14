"""onTong FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.config import settings
from backend.core.logging_config import setup_logging, generate_request_id, request_id_var
from backend.core.auth.factory import create_auth_provider
from backend.core.auth.deps import init_auth
from backend.infrastructure.storage.factory import create_storage
from backend.infrastructure.vectordb.chroma import chroma
from backend.application.wiki.wiki_indexer import WikiIndexer
from backend.application.wiki.wiki_search import WikiSearchService
from backend.application.wiki.wiki_service import WikiService
from backend.application.conflict.conflict_store import create_conflict_store
from backend.application.conflict.conflict_service import ConflictDetectionService
from backend.application.agent.registry import registry
from backend.application.agent.skill import skill_registry
from backend.application.agent.skills import register_all_skills
from backend.application.agent.rag_agent import RAGAgent
from backend.application.trust.confidence_service import ConfidenceService
from backend.application.trust.citation_tracker import create_citation_tracker
from backend.application.trust.feedback_tracker import create_feedback_tracker
from backend.application.agent.simulator_agent import SimulatorAgent
from backend.application.agent.tracer_agent import TracerAgent
from backend.api import wiki as wiki_api
from backend.api import search as search_api
from backend.api import agent as agent_api
from backend.api import approval as approval_api
from backend.api import files as files_api
from backend.api import metadata as metadata_api
from backend.api import conflict as conflict_api
from backend.api import lock as lock_api
from backend.api import acl as acl_api
from backend.api import skill as skill_api
from backend.api import persona as persona_api
from backend.api import auth as auth_api
from backend.api import graph as graph_api
from backend.api import group as group_api
from backend.application.graph.graph_store import create_graph_store
from backend.application.graph.graph_builder import GraphBuilder
from backend.application.skill.skill_loader import UserSkillLoader
from backend.application.skill.skill_matcher import SkillMatcher
from backend.infrastructure.events.event_bus import event_bus
from backend.modeling.api import modeling as modeling_api
from backend.simulation.api import simulation as simulation_api
from backend.simulation.client.modeling_client import create_modeling_client
from backend.simulation.client.config import use_mock as simulation_use_mock

setup_logging(
    level=settings.log_level,
    json_format=settings.environment != "development",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("onTong Backend starting up...")

    # Initialize auth
    auth_provider = create_auth_provider(settings.auth_provider)
    await auth_provider.on_startup()
    init_auth(auth_provider)
    logger.info(f"Auth provider: {settings.auth_provider}")

    # Initialize storage
    storage = create_storage()
    logger.info(f"Wiki storage: {settings.storage_backend} -> {settings.wiki_dir}")

    # Initialize ChromaDB
    chroma.connect()

    # Build services
    indexer = WikiIndexer(chroma)
    search_service = WikiSearchService()
    wiki_service = WikiService(storage, indexer, search_service)

    # Build materialized metadata index (auto-build if missing)
    from backend.application.metadata.metadata_index import MetadataIndex
    from backend.application.metadata.tag_registry import tag_registry
    meta_index = MetadataIndex(settings.wiki_dir)
    wiki_service.set_metadata_index(meta_index)
    if not meta_index._path.exists():
        _files = await wiki_service.get_all_files()
        meta_index.rebuild(extended=[
            {
                "path": f.path,
                "domain": f.metadata.domain,
                "process": f.metadata.process,
                "tags": f.metadata.tags,
                "updated": f.metadata.updated,
                "updated_by": f.metadata.updated_by,
                "created_by": f.metadata.created_by,
                "related": f.metadata.related,
                "status": f.metadata.status,
                "supersedes": f.metadata.supersedes,
                "superseded_by": f.metadata.superseded_by,
            }
            for f in _files
        ])
        logger.info("Metadata index auto-built on startup")

    # Initialize semantic tag registry (same embedding as wiki collection)
    if chroma._client:
        from backend.infrastructure.vectordb.chroma import _get_embedding_function
        tag_registry.connect(chroma._client, _get_embedding_function())
        # Sync existing tags from index to registry
        idx_data = meta_index._load()
        tag_counts = idx_data.get("tags", {})
        if tag_counts and tag_registry.is_connected:
            tag_registry.register_tags_bulk(tag_counts)

    # Wire metadata service dependencies
    from backend.application.metadata import metadata_service as meta_svc
    meta_svc.init(meta_index, tag_registry)

    # Build feedback tracker (before confidence service, which uses it)
    feedback_tracker = create_feedback_tracker()

    # Build citation tracker and confidence scoring service
    citation_tracker = create_citation_tracker()
    confidence_svc = ConfidenceService(meta_index, settings.wiki_dir)
    confidence_svc.set_citation_tracker(citation_tracker)
    confidence_svc.set_chroma(chroma)
    confidence_svc.set_feedback_tracker(feedback_tracker)

    # Build conflict detection service
    conflict_store = create_conflict_store()
    conflict_svc = ConflictDetectionService(chroma, conflict_store)
    wiki_service.set_conflict_service(conflict_svc)
    wiki_service.set_chroma(chroma)
    wiki_service.set_confidence_service(confidence_svc)

    # Build digest service
    from backend.application.trust.digest import DocumentDigestService
    digest_svc = DocumentDigestService(confidence_svc, conflict_svc, settings.wiki_dir)

    # Build knowledge graph
    graph_store = create_graph_store()
    graph_builder = GraphBuilder(
        graph_store=graph_store,
        meta_index=meta_index,
        conflict_store=conflict_store,
        citation_tracker=citation_tracker,
    )

    # Invalidate caches on tree_change events (100K-scale: avoid stale data)
    def _on_tree_change(data: dict) -> None:
        path = data.get("path", "")
        if path:
            confidence_svc.invalidate(path)
            graph_builder.rebuild_file(path)
        digest_svc.invalidate_cache()

    event_bus.on("tree_change", _on_tree_change)

    # Wire up API modules
    graph_api.init(graph_store, graph_builder)
    wiki_api.init(wiki_service, confidence_service=confidence_svc, digest_service=digest_svc, feedback_tracker=feedback_tracker)
    search_api.init(wiki_service, search_service, chroma, confidence_service=confidence_svc)
    approval_api.init(wiki_service)
    metadata_api.init(wiki_service, meta_index)
    # Initialize user-facing skill system
    skill_loader = UserSkillLoader(storage)
    skill_matcher = SkillMatcher()

    agent_api.init(wiki_service, chroma=chroma, storage=storage,
                   skill_loader=skill_loader, skill_matcher=skill_matcher,
                   conflict_store=conflict_store, meta_index=meta_index)
    skill_api.init(skill_loader, skill_matcher, storage)
    persona_api.init(storage)
    conflict_api.init(wiki_service, conflict_svc)

    # Initialize group store and group API
    from backend.core.auth.group_store import JSONGroupStore
    from pathlib import Path
    group_store = JSONGroupStore(path=Path("data/groups.json"))
    group_api.init(group_store)

    # Initialize Section 2 (Modeling) with Neo4j
    from backend.modeling.infrastructure.neo4j_client import Neo4jClient
    try:
        neo4j_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
        neo4j_health = neo4j_client.health()
        logger.info(f"Neo4j: {neo4j_health['status']}")
        modeling_api.init(neo4j_client=neo4j_client)
    except Exception as e:
        logger.warning(f"Neo4j unavailable, modeling in limited mode: {e}")
        modeling_api.init()

    # Initialize Section 3 (Simulation) API
    sim_client = create_modeling_client(use_mock=simulation_use_mock())
    simulation_api.init(sim_client)

    # Register skills (before agents — agents may use them)
    register_all_skills()
    logger.info(f"Registered skills: {len(skill_registry.list_skills())} skills")

    # Register default hooks
    from backend.application.agent.hooks import register_default_hooks
    register_default_hooks()

    # Register agents
    rag_agent = RAGAgent(chroma, storage=storage)
    rag_agent.set_confidence_service(confidence_svc)
    rag_agent.set_citation_tracker(citation_tracker)
    registry.register(rag_agent)
    registry.register(SimulatorAgent())
    registry.register(TracerAgent())
    logger.info(f"Registered agents: {registry.list_agents()}")

    # Background indexing — app is immediately available
    async def _bg_initial_index():
        try:
            files = await wiki_service.get_all_files()
            total = len(files)
            indexed = 0
            batch_size = 100
            for i in range(0, total, batch_size):
                batch = files[i:i + batch_size]
                for f in batch:
                    await wiki_service.indexer.index_file(f)
                    indexed += 1
                # Yield to event loop between batches
                await asyncio.sleep(0)
            logger.info(f"Background indexing complete: {indexed}/{total} files")

            # Populate conflict store after indexing
            logger.info("Populating conflict store...")
            await asyncio.to_thread(conflict_svc.full_scan)
            logger.info("Conflict store populated")

            # Build knowledge graph from metadata + conflicts
            logger.info("Building knowledge graph...")
            rel_count = await asyncio.to_thread(graph_builder.rebuild_all)
            logger.info(f"Knowledge graph built: {rel_count} relationships")
        except Exception as e:
            logger.warning(f"Background indexing failed: {e}")

    import asyncio
    asyncio.create_task(_bg_initial_index())
    logger.info("Background indexing started (app available immediately)")

    yield

    await auth_provider.on_shutdown()
    logger.info("onTong Backend shutting down...")


app = FastAPI(
    title="onTong Backend",
    description="Knowledge-Fused Multi-Agent Platform for SCM",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# CORS — explicit whitelist (no wildcards)
_cors_origins = [settings.frontend_url]
if settings.environment == "development":
    _cors_origins.append("http://localhost:3000")
    _cors_origins.append("http://localhost:3001")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)


# Request ID middleware
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("X-Request-ID") or generate_request_id()
        request_id_var.set(rid)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


app.add_middleware(RequestIdMiddleware)

# Register routers
app.include_router(wiki_api.router)
app.include_router(search_api.router)
app.include_router(agent_api.router)
app.include_router(approval_api.router)
app.include_router(files_api.router)
app.include_router(metadata_api.router)
app.include_router(conflict_api.router)
app.include_router(lock_api.router)
app.include_router(acl_api.router)
app.include_router(skill_api.router)
app.include_router(persona_api.router)
app.include_router(auth_api.router)
app.include_router(graph_api.router)
app.include_router(group_api.router)
app.include_router(modeling_api.router)
app.include_router(simulation_api.router)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.get("/health")
async def health():
    from backend.application.wiki.wiki_service import index_status
    return {
        "status": "healthy",
        "version": "0.1.0",
        "chroma_connected": chroma.is_connected,
        "chroma_docs": chroma.count(),
        "agents": registry.list_agents(),
        "indexing_pending": index_status.pending_count(),
        "sse_subscribers": event_bus.subscriber_count,
    }


@app.get("/api/events")
async def sse_events():
    """Server-Sent Events endpoint for real-time updates."""
    from starlette.responses import StreamingResponse

    async def stream():
        yield "event: connected\ndata: {}\n\n"
        async for event in event_bus.subscribe():
            yield event.to_sse()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=settings.environment == "development",
    )
