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
from backend.application.image.analyzer import ImageAnalyzer
from backend.application.image.ocr_engine import OCREngine
from backend.application.image.vision_provider import create_vision_provider
from backend.application.image.queue import ImageProcessingQueue
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
# 2026-05-01 clean slate: backend.modeling (Section 2) 만 본 process 가 책임.
# Section 3 (simulation) 은 plug-in 방식 — 별 PR 로 추가.
# 인계 명세는 toClaude/modeling/handoff-spec/ 6 파일 (00 README + 01~05) 참조.
# C2~C5 완료 (2026-05-02): Code/Domain/Mapping Layer + Query API.
# Section 3 통합 (2026-05-10): simulation router 8종 등록 (sandbox/jobs/runs/bridge/transpile/auto_pr/differential).
from backend.api import authoring as authoring_api
from backend.modeling.api import ontology_router as ontology_query_api
from backend.modeling.api import graph_api as ontology_graph_api
from backend.modeling.api import modules_api as ontology_modules_api
from backend.modeling.api import perspective_api
from backend.modeling.api import queue_actions_api
from backend.modeling.api import recommend_api
from backend.modeling.api import repo_import as repo_import_api
from backend.modeling.persistence.database import bootstrap_database
# 2026-05-12 (Phase 1): Section 3 agent 의 단일 진입점. POST /api/modeling/ontology/query
# (intent: impact_analysis / simulate / explain) + GET /graph/stats + /term/search.
from backend.modeling.ontology.api.ontology_router import router as modeling_ontology_query_router
# 2026-05-12 (Phase 2): Section 3 4 agent (bridge chat / sandbox / code-impact / data-impact).
# 모든 agent 는 위 /api/modeling/ontology/* 만 호출 (Neo4j 직접 의존 0건).
from backend.section3.api.router import router as section3_router
# Section 3 (simulation) — 2026-05-12 zero 재개편. 옛 simulation router 모두 삭제.
# 새 구현은 backend/section3/ 에 들어갈 예정 (Phase 2~).

setup_logging(
    level=settings.log_level,
    json_format=settings.environment != "development",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("onTong Backend starting up...")

    # Initialize group store (before auth, so provider can resolve groups)
    from backend.core.auth.group_store import JSONGroupStore
    from pathlib import Path
    group_store = JSONGroupStore(path=Path("data/groups.json"))
    group_api.init(group_store)

    # Initialize auth (pass group_store for group resolution)
    auth_provider = create_auth_provider(
        settings.auth_provider, group_store=group_store
    )
    await auth_provider.on_startup()
    init_auth(auth_provider)
    logger.info(f"Auth provider: {settings.auth_provider}")

    # Initialize storage
    storage = create_storage()
    logger.info(f"Wiki storage: {settings.storage_backend} -> {settings.wiki_dir}")

    # Initialize ChromaDB
    chroma.connect()

    # Resolve fulltext backend via the profile factory (BM25 in dev, ES in enterprise).
    # Done before WikiIndexer so the indexer doesn't reach into bm25_index directly.
    from backend.core.backends import get_fulltext_search
    _ft_profile = settings.resolve_profile()
    fulltext = get_fulltext_search(_ft_profile, es_url=settings.es_url)
    logger.info(f"FullText backend: {_ft_profile.fulltext_backend}")

    # Build services
    indexer = WikiIndexer(chroma, fulltext)
    search_service = WikiSearchService()
    wiki_service = WikiService(storage, indexer, search_service)

    # Build materialized metadata index (auto-build if missing)
    from backend.application.metadata.metadata_index import MetadataIndex
    from backend.application.metadata.tag_registry import tag_registry
    meta_index = MetadataIndex(settings.wiki_dir)
    wiki_service.set_metadata_index(meta_index)
    if meta_index.is_empty():
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

    # Initialize image analysis pipeline (if enabled)
    if settings.image_analysis_enabled:
        _ocr = OCREngine(
            languages=settings.image_ocr_languages.split(","),
            gpu=settings.image_ocr_gpu,
            confidence_threshold=settings.image_ocr_confidence,
        )
        _vision = create_vision_provider(
            provider=settings.image_vision_provider,
            model=settings.image_vision_model,
            ollama_url=settings.ollama_host,
            api_key=settings.anthropic_api_key,
        )
        _img_analyzer = ImageAnalyzer(ocr=_ocr, vision=_vision)
        _img_queue = ImageProcessingQueue(_img_analyzer)
        wiki_service.set_image_queue(_img_queue)
        logger.info(
            f"Image analysis: OCR={settings.image_ocr_engine}, "
            f"Vision={settings.image_vision_provider}/{settings.image_vision_model}"
        )

    # Image Registry — in-memory hash index + ref counting
    from backend.application.image.image_registry import ImageRegistry
    from backend.api.files import set_image_registry
    _image_registry = ImageRegistry()
    _image_registry.scan(Path(settings.wiki_dir))
    set_image_registry(_image_registry)

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

    # Image ref count cleanup on document deletion
    def _on_tree_change_image_refs(data: dict) -> None:
        action = data.get("action")
        path = data.get("path", "")
        if not path.endswith(".md"):
            return
        if action == "remove":
            _image_registry.remove_all_refs_for_doc(path)
            logger.debug(f"Image refs cleared for deleted doc: {path}")

    event_bus.on("tree_change", _on_tree_change_image_refs)

    # Recompute access_scope in ChromaDB when ACL changes
    async def _on_acl_changed(data: dict):
        path = data.get("path", "")
        if not path:
            return
        from backend.core.auth.acl_store import acl_store
        from backend.core.auth.scope import format_scope_for_chroma
        scope = acl_store.compute_access_scope(path)
        access_scope = {
            "read": format_scope_for_chroma(scope["read"]),
            "write": format_scope_for_chroma(scope["write"]),
        }
        updated = await indexer.update_access_scope(path, access_scope)
        if updated:
            logger.info("ACL changed for %s: updated %d chunks", path, updated)

    event_bus.on("acl_changed", _on_acl_changed)

    # Wire up API modules
    graph_api.init(graph_store, graph_builder)
    wiki_api.init(wiki_service, confidence_service=confidence_svc, digest_service=digest_svc, feedback_tracker=feedback_tracker)
    search_api.init(wiki_service, search_service, chroma, confidence_service=confidence_svc, meta_index=meta_index)
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


    # 2026-05-02 C2~C5 — Ontology Core 시작 (SQLite bootstrap + Query API client init)
    # ORM modules 를 import 해야 Base.metadata 에 등록됨
    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401
    bootstrap_database()
    ontology_query_api.init()
    logger.info("Ontology Core wired: Code/Domain/Mapping Layer + Query API")

    # Authoring AI — interview-driven ontology authoring (B.5 prototype, 2026-05-05)
    from backend.modeling.domain_layer.store import DomainLayerStore
    authoring_api.init(business_term_store=DomainLayerStore())
    logger.info("Authoring AI wired: 8 capabilities + session + cost log")

    # Section 3 (Simulation) — Agent 3종 (agents_router) + SlabViewer3D 보존 라우터.
    # 별도 init() 불필요 — OntologyClient는 in-process 모드로 Section 2를 직접 호출.

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

    # Start event bus before any tasks that may publish events
    await event_bus.start()
    logger.info("EventBus started")

    # Phase 1: initialize RefIndex (creates SQLite file or pings Postgres)
    try:
        from backend.core.config import settings as _cfg
        from backend.core.backends import get_ref_index
        _profile = _cfg.resolve_profile()
        if _profile.ref_index_backend == "sqlite":
            from pathlib import Path as _Path
            _sqlite_path = _Path(_cfg.wiki_dir) / ".ontong" / "refs.db"
            _sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            get_ref_index(_profile, sqlite_path=str(_sqlite_path))
        elif _cfg.postgres_dsn:
            get_ref_index(_profile, postgres_dsn=_cfg.postgres_dsn)
        logger.info(f"RefIndex initialized: {_profile.ref_index_backend}")
    except Exception as e:
        logger.warning(f"RefIndex init failed (will retry per-request): {e}")

    # Phase 2: initialize VersionStore (OCC — creates SQLite file or pings Postgres)
    try:
        from backend.core.backends import get_version_store
        _vs_profile = _cfg.resolve_profile()
        if _vs_profile.version_store_backend == "sqlite":
            from pathlib import Path as _VSPath
            _vs_sqlite_path = _VSPath(_cfg.wiki_dir) / ".ontong" / "versions.db"
            _vs_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            get_version_store(_vs_profile, sqlite_path=str(_vs_sqlite_path))
        elif _cfg.postgres_dsn:
            get_version_store(_vs_profile, postgres_dsn=_cfg.postgres_dsn)
        logger.info(f"VersionStore initialized: {_vs_profile.version_store_backend}")
    except Exception as e:
        logger.warning(f"VersionStore init failed (will retry per-request): {e}")

    # Phase 3: initialize AuditStore (rename audit/jobs)
    try:
        from backend.core.backends import get_audit_store
        _as_profile = _cfg.resolve_profile()
        if _as_profile.audit_store_backend == "sqlite":
            from pathlib import Path as _ASPath
            _as_sqlite_path = _ASPath(_cfg.wiki_dir) / ".ontong" / "audit.db"
            _as_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            get_audit_store(_as_profile, sqlite_path=str(_as_sqlite_path))
        elif _cfg.postgres_dsn:
            get_audit_store(_as_profile, postgres_dsn=_cfg.postgres_dsn)
        logger.info(f"AuditStore initialized: {_as_profile.audit_store_backend}")
    except Exception as e:
        logger.warning(f"AuditStore init failed (will retry per-request): {e}")

    import asyncio
    asyncio.create_task(_bg_initial_index())
    logger.info("Background indexing started (app available immediately)")

    yield

    await event_bus.stop()
    logger.info("EventBus stopped")
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
    # localhost + 127.0.0.1 둘 다 — Next dev 가 양쪽 어느 origin 으로든 서빙 가능.
    # P12 (2026-04-25) : 127.0.0.1 누락으로 CORS preflight 실패 회귀 수정.
    _cors_origins.extend([
        "http://localhost:3000", "http://localhost:3001",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001",
    ])

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
# 2026-05-02 C5 — Ontology Query API (Agent boundary)
app.include_router(ontology_query_api.router)
app.include_router(repo_import_api.router)
app.include_router(recommend_api.router)
app.include_router(ontology_graph_api.router)
app.include_router(ontology_modules_api.router)
app.include_router(perspective_api.router)
app.include_router(queue_actions_api.router)
# Authoring AI (2026-05-05 — B.5 prototype)
app.include_router(authoring_api.router)
# Section 3 (simulation) — 2026-05-12 zero 재개편. 옛 simulation router 모두 삭제.
# 새 router 는 Phase 2 에서 backend/section3/ 신설 후 등록.
# Phase 1 (2026-05-12): modeling 의 ontology query router 등록 — Section 3 agent 의 단일 진입점.
app.include_router(modeling_ontology_query_router)
# Phase 2 (2026-05-12): Section 3 4 agent — /api/section3/* (chat / sandbox / code-impact / data-impact).
app.include_router(section3_router)


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
