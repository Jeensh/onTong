"""RAG Pipeline Latency Benchmark.

Measures wall-clock time for each stage of the RAG pipeline:
  - Routing (keyword vs LLM fallback)
  - Query augmentation (sequential vs parallel)
  - Vector search
  - Clarity check (rule-based)
  - Cognitive reflection
  - Final answer generation (time to first token)

Usage:
    cd /path/to/onTong
    source venv/bin/activate
    python -m tests.bench_rag_latency
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field

from backend.application.agent.router import MainRouter
from backend.infrastructure.vectordb.chroma import ChromaWrapper


@dataclass
class StageResult:
    name: str
    elapsed_ms: float
    detail: str = ""


@dataclass
class BenchmarkResult:
    query: str
    stages: list[StageResult] = field(default_factory=list)
    total_ms: float = 0.0


# Representative queries covering different routing paths
BENCHMARK_QUERIES: list[dict] = [
    # Keyword-routable (should NOT hit LLM)
    {"message": "후판 공정계획 담당자 알려줘", "label": "keyword-wiki"},
    {"message": "DG320 에러 대응 방법", "label": "keyword-wiki"},
    {"message": "OJT 진행 절차", "label": "keyword-wiki"},
    {"message": "재고관리 프로세스 설명해줘", "label": "keyword-wiki"},
    {"message": "출장 경비 규정", "label": "keyword-wiki"},
    # Previously ambiguous (catch-all should handle now)
    {"message": "지난 주 회의 결과", "label": "catch-all"},
    {"message": "서버 점검", "label": "catch-all"},
    {"message": "김태헌", "label": "catch-all"},
    # Very short / vague (tests clarity check path)
    {"message": "알려줘", "label": "vague"},
    {"message": "뭐야", "label": "vague"},
    # English (may hit LLM fallback)
    {"message": "What is onTong?", "label": "english"},
    # Follow-up simulation (tests augmentation)
    {
        "message": "담당자 누구야",
        "label": "followup",
        "history": [
            {"role": "user", "content": "후판 공정계획 알려줘"},
            {"role": "assistant", "content": "후판 공정계획은 제강/압연 공정의 생산 스케줄링 업무입니다."},
        ],
    },
]


async def bench_routing(router: MainRouter, message: str) -> StageResult:
    t0 = time.perf_counter()
    decision = await router.route(message)
    elapsed = (time.perf_counter() - t0) * 1000
    return StageResult(
        "routing", elapsed,
        f"{decision.agent} conf={decision.confidence:.2f} ({decision.reasoning[:40]})"
    )


async def bench_vector_search(chroma: ChromaWrapper, query: str) -> StageResult:
    t0 = time.perf_counter()
    results = chroma.query(query_text=query, n_results=8)
    elapsed = (time.perf_counter() - t0) * 1000
    doc_count = len(results.get("documents", [[]])[0])
    distances = results.get("distances", [[]])[0]
    best_rel = max(0, 1 - min(distances)) if distances else 0
    return StageResult("vector_search", elapsed, f"{doc_count} docs, best_rel={best_rel:.0%}")


async def bench_augmentation_sequential(
    router: MainRouter, message: str, history: list[dict]
) -> tuple[StageResult, StageResult]:
    """Measure routing + augmentation sequentially."""
    from backend.application.agent.rag_agent import RAGAgent

    chroma = ChromaWrapper()
    agent = RAGAgent(chroma=chroma)

    t0 = time.perf_counter()
    decision = await router.route(message)
    route_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    augmented = await agent._augment_query(message, history)
    aug_ms = (time.perf_counter() - t0) * 1000

    return (
        StageResult("routing_seq", route_ms, decision.agent),
        StageResult("augment_seq", aug_ms, f"'{message}' → '{augmented}'"),
    )


async def bench_augmentation_parallel(
    router: MainRouter, message: str, history: list[dict]
) -> tuple[StageResult, float]:
    """Measure routing + augmentation in parallel."""
    from backend.application.agent.rag_agent import RAGAgent

    chroma = ChromaWrapper()
    agent = RAGAgent(chroma=chroma)

    t0 = time.perf_counter()
    decision, augmented = await asyncio.gather(
        router.route(message),
        agent._augment_query(message, history),
    )
    parallel_ms = (time.perf_counter() - t0) * 1000

    return (
        StageResult("parallel_total", parallel_ms, f"{decision.agent} + '{augmented}'"),
        parallel_ms,
    )


async def main() -> None:
    router = MainRouter()
    chroma = ChromaWrapper()

    print("=" * 72)
    print("  RAG Pipeline Latency Benchmark")
    print("=" * 72)

    all_routing_ms: list[float] = []
    all_search_ms: list[float] = []
    keyword_hit = 0
    llm_fallback = 0

    for qc in BENCHMARK_QUERIES:
        msg = qc["message"]
        label = qc.get("label", "")
        print(f"\n--- [{label}] {msg}")

        # Routing
        r = await bench_routing(router, msg)
        print(f"  {r.name:20s} {r.elapsed_ms:8.1f}ms  {r.detail}")
        all_routing_ms.append(r.elapsed_ms)
        if "keyword_match" in r.detail:
            keyword_hit += 1
        elif "llm_classification" in r.detail:
            llm_fallback += 1

        # Vector search
        s = await bench_vector_search(chroma, msg)
        print(f"  {s.name:20s} {s.elapsed_ms:8.1f}ms  {s.detail}")
        all_search_ms.append(s.elapsed_ms)

    # Parallel vs sequential comparison for follow-up queries
    followup_queries = [q for q in BENCHMARK_QUERIES if q.get("history")]
    if followup_queries:
        print(f"\n{'=' * 72}")
        print("  Parallel vs Sequential: Routing + Query Augmentation")
        print(f"{'=' * 72}")

        for qc in followup_queries:
            msg = qc["message"]
            history = qc["history"]
            print(f"\n  Query: {msg}")

            seq_route, seq_aug = await bench_augmentation_sequential(router, msg, history)
            seq_total = seq_route.elapsed_ms + seq_aug.elapsed_ms
            print(f"    Sequential: routing={seq_route.elapsed_ms:.1f}ms + augment={seq_aug.elapsed_ms:.1f}ms = {seq_total:.1f}ms")

            par_result, par_ms = await bench_augmentation_parallel(router, msg, history)
            print(f"    Parallel:   total={par_ms:.1f}ms")

            savings = seq_total - par_ms
            print(f"    Savings:    {savings:.1f}ms ({savings / seq_total * 100:.0f}%)" if seq_total > 0 else "")

    # Summary
    print(f"\n{'=' * 72}")
    print("  Summary")
    print(f"{'=' * 72}")
    print(f"  Queries tested:     {len(BENCHMARK_QUERIES)}")
    print(f"  Keyword hits:       {keyword_hit}/{len(BENCHMARK_QUERIES)}")
    print(f"  LLM fallbacks:      {llm_fallback}/{len(BENCHMARK_QUERIES)}")
    print(f"  Routing mean:       {statistics.mean(all_routing_ms):.1f}ms")
    if len(all_routing_ms) > 1:
        print(f"  Routing p95:        {sorted(all_routing_ms)[int(len(all_routing_ms) * 0.95)]:.1f}ms")
    print(f"  Vector search mean: {statistics.mean(all_search_ms):.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
