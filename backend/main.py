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
from backend.application.skill.skill_loader import UserSkillLoader
from backend.application.skill.skill_matcher import SkillMatcher
from backend.infrastructure.events.event_bus import event_bus
from backend.modeling.api import modeling as modeling_api
from backend.simulation.api import simulation as simulation_api
from backend.simulation.api.slab_agent import router as slab_agent_router
from backend.simulation.api.custom_agent import router as custom_agent_router
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

    # Build conflict detection service
    conflict_store = create_conflict_store()
    conflict_svc = ConflictDetectionService(chroma, conflict_store)
    wiki_service.set_conflict_service(conflict_svc)

    # Wire up API modules
    wiki_api.init(wiki_service)
    search_api.init(wiki_service, search_service, chroma)
    approval_api.init(wiki_service)
    metadata_api.init(wiki_service)
    # Initialize user-facing skill system
    skill_loader = UserSkillLoader(storage)
    skill_matcher = SkillMatcher()

    agent_api.init(wiki_service, chroma=chroma, storage=storage,
                   skill_loader=skill_loader, skill_matcher=skill_matcher,
                   conflict_store=conflict_store)
    skill_api.init(skill_loader, skill_matcher, storage)
    conflict_api.init(wiki_service, conflict_svc)

    # Initialize Section 2 (Modeling) and Section 3 (Simulation) APIs
    modeling_api.init()
    sim_client = create_modeling_client(use_mock=simulation_use_mock())
    simulation_api.init(sim_client)

    # Register skills (before agents — agents may use them)
    register_all_skills()
    logger.info(f"Registered skills: {len(skill_registry.list_skills())} skills")

    # Register agents
    registry.register(RAGAgent(chroma, storage=storage))
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
app.include_router(modeling_api.router)
app.include_router(simulation_api.router)
app.include_router(slab_agent_router)
app.include_router(custom_agent_router)


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
