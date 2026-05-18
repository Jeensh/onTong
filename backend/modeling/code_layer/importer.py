"""Repo Import 파이프라인 — Java repo path → CodeType/CodeMethod/CallSite 적재.

P3-2: 데모 repo (sample-repos/slab-design-real) 같은 실제 Maven multi-module 프로젝트를
backend 분석 + Code Layer 적재. 비동기 + 진행률 publish 가능.

흐름:
  1) Java 파일 walk (target/, .git/ 제외)
  2) JavaParser + Spring 10 analyzer 호출 → ParseResult per file
  3) adapter.adapt_parse_results → CodeType list
  4) role_classifier.classify_roles → role 자동 분류
  5) callsite_analyzer.analyze_call_sites → 호출 사이트 mock seed (Phase 1 — 향후 실제 추출)
  6) CodeLayerStore.delete_repo + upsert_types + upsert_call_sites

진행률은 ImportJob 객체의 progress callback 으로 publish.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import ParseResult
from backend.modeling.code_analysis.spring import (
    AopAnalyzer,
    BeanUtilsAnalyzer,
    ConfigPropertiesAnalyzer,
    DIAnalyzer,
    EventsAnalyzer,
    HttpAnalyzer,
    JpaAnalyzer,
    MapStructAnalyzer,
    NativeSqlAnalyzer,
    ProfileAnalyzer,
    ScheduledAnalyzer,
)
from backend.modeling.code_layer.adapter import adapt_parse_results
from backend.modeling.code_layer.callsite_analyzer import analyze_call_sites
from backend.modeling.code_layer.role_classifier import classify_roles
from backend.modeling.code_layer.schema import CallSite
from backend.modeling.code_layer.store import CodeLayerStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ImportJob — 진행 상태
# ---------------------------------------------------------------------------
@dataclass
class ImportJob:
    """Import 1회의 lifecycle 추적."""
    id: str
    repo_id: str
    repo_path: str
    status: str = "pending"            # pending | parsing | adapting | classifying | storing | done | error
    files_total: int = 0
    files_parsed: int = 0
    types_extracted: int = 0
    methods_extracted: int = 0
    call_sites_extracted: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    message: str = ""

    @property
    def duration_ms(self) -> int:
        end = self.finished_at if self.finished_at else time.time()
        return int((end - self.started_at) * 1000)

    @property
    def progress_pct(self) -> int:
        if self.status == "done":
            return 100
        if self.status == "error":
            return 0
        if self.files_total == 0:
            return 0
        # parsing 단계만 0~80%, 나머지 단계 80~100%
        parsing_done = (self.files_parsed / self.files_total) * 80
        if self.status in ("parsing", "pending"):
            return int(parsing_done)
        if self.status == "adapting":
            return 82
        if self.status == "classifying":
            return 86
        if self.status == "storing":
            return 95
        return int(parsing_done)


# ---------------------------------------------------------------------------
# Java 파일 walker
# ---------------------------------------------------------------------------
_SKIP_DIRS = {"target", ".git", ".idea", "node_modules", "build", ".gradle", "dist"}


def find_java_files(root: Path) -> list[Path]:
    """Java 파일 list (target/.git 등 제외)."""
    out: list[Path] = []
    if not root.exists() or not root.is_dir():
        return out
    for p in root.rglob("*.java"):
        # skip if any parent dir matches _SKIP_DIRS
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


# ---------------------------------------------------------------------------
# Spring analyzers — 11종 풀세트
# ---------------------------------------------------------------------------
def _make_spring_analyzers():
    return [
        DIAnalyzer(),
        AopAnalyzer(),
        HttpAnalyzer(),
        EventsAnalyzer(),
        ScheduledAnalyzer(),
        ProfileAnalyzer(),
        JpaAnalyzer(),
        MapStructAnalyzer(),
        BeanUtilsAnalyzer(),
        NativeSqlAnalyzer(),
        ConfigPropertiesAnalyzer(),
    ]


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------
class RepoImporter:
    """Repo path → CodeType/CodeMethod/CallSite import 메인 클래스."""

    def __init__(self, store: CodeLayerStore | None = None) -> None:
        self.store = store or CodeLayerStore()

    def run(
        self,
        job: ImportJob,
        *,
        on_update: Callable[[ImportJob], None] | None = None,
    ) -> ImportJob:
        """동기 실행. 진행률 발행은 on_update callback 호출."""
        job.started_at = time.time()
        job.status = "parsing"
        if on_update:
            on_update(job)

        try:
            return self._run_inner(job, on_update)
        except Exception as e:
            logger.exception("RepoImporter failed for repo_path=%s", job.repo_path)
            job.status = "error"
            job.errors.append(str(e))
            job.finished_at = time.time()
            job.message = f"import 실패: {e}"
            if on_update:
                on_update(job)
            return job

    def _run_inner(
        self,
        job: ImportJob,
        on_update: Callable[[ImportJob], None] | None,
    ) -> ImportJob:
        repo_path = Path(job.repo_path)
        files = find_java_files(repo_path)
        job.files_total = len(files)
        job.message = f"{len(files)} Java 파일 발견"
        if on_update:
            on_update(job)

        if not files:
            job.status = "done"
            job.finished_at = time.time()
            job.message = "Java 파일 없음 — repo_path 확인 필요"
            if on_update:
                on_update(job)
            return job

        # 1. Parse — Spring analyzer 풀세트로
        parser = JavaParser(spring_analyzers=_make_spring_analyzers())
        results: list[ParseResult] = []
        for i, fp in enumerate(files, start=1):
            try:
                content = fp.read_text(encoding="utf-8")
                pr = parser.parse_file(fp, content)
                results.append(pr)
                if pr.errors:
                    job.errors.extend(f"{fp.name}: {e}" for e in pr.errors[:2])
            except Exception as e:
                job.errors.append(f"{fp.name}: parse error — {e}")
                logger.warning("parse failed: %s — %s", fp, e)
                continue
            job.files_parsed = i
            # progress publish 매 10 파일 (또는 마지막)
            if on_update and (i % 10 == 0 or i == len(files)):
                on_update(job)

        # 2. Adapt
        job.status = "adapting"
        job.message = "ParseResult → CodeType 매핑 중..."
        if on_update:
            on_update(job)
        types = adapt_parse_results(results, repo_id=job.repo_id)
        job.types_extracted = len(types)
        job.methods_extracted = sum(len(t.methods) for t in types)

        # 3. Role 자동 분류 (slab-design 도메인 패턴 활용)
        job.status = "classifying"
        job.message = f"{len(types)} CodeType role 분류 중..."
        if on_update:
            on_update(job)
        types = classify_roles(types)

        # 4. CallSite — 메서드 본체의 calls relation 에서 seed 추출
        # Gap 5 chain resolution: for `a.b().c()` look up `b()`'s return type
        # and propagate it as `c()`'s receiver_type (mutates relation attrs).
        self._resolve_chain_receivers(results, types)
        seeds_raw = self._extract_call_seeds(results)
        # parser 의 caller_fqn (signature 없음) 을 저장된 method fqn (signature 포함) 으로 매핑
        # → CallSite.caller_method_fqn FK 가 code_methods.fqn 와 정합.
        seeds = self._normalize_caller_fqns(seeds_raw, types)
        sites = analyze_call_sites(types, seeds=seeds, repo_id=job.repo_id)
        job.call_sites_extracted = len(sites)

        # 5. Store
        job.status = "storing"
        job.message = "SQLite 저장 중..."
        if on_update:
            on_update(job)
        self.store.delete_repo(job.repo_id)
        self.store.upsert_types(repo_id=job.repo_id, code_types=types)
        if sites:
            self.store.upsert_call_sites(repo_id=job.repo_id, call_sites=sites)

        job.status = "done"
        job.finished_at = time.time()
        job.message = (
            f"완료: {job.types_extracted} CodeType, {job.methods_extracted} method, "
            f"{job.call_sites_extracted} call site, {job.duration_ms}ms"
        )
        if on_update:
            on_update(job)
        return job

    @staticmethod
    def _normalize_caller_fqns(
        seeds: list[tuple[str, str, str, int | None]],
        types: list,
    ) -> list[tuple[str, str, str, int | None]]:
        """seed 의 caller_fqn 을 실제 저장된 CodeMethod.fqn 으로 치환.

        parser 가 emit 하는 r.source 는 `Pkg.Class.method` (signature 없음). 우리 schema 는
        오버로드 구분을 위해 `Pkg.Class.method(int,String)` 형식으로 저장. line 으로 매칭
        — caller fqn prefix 가 일치하고 line_start <= line <= line_end 인 method 채택.

        매칭 실패 시 seed 를 drop (orphan FK 방지).
        """
        # method base_fqn (signature 제거) → list of (stored_fqn, line_start, line_end)
        index: dict[str, list[tuple[str, int, int]]] = {}
        for t in types:
            for m in t.methods:
                base = m.fqn.split("(", 1)[0]
                # @lineN suffix (dedup) 도 제거
                base = base.split("@line", 1)[0]
                index.setdefault(base, []).append(
                    (m.fqn, m.line_start or 0, m.line_end or 10**9)
                )

        out: list[tuple[str, str, str, int | None]] = []
        for caller_fqn, callee, recv, line in seeds:
            base = caller_fqn.split("(", 1)[0].split("@line", 1)[0]
            cands = index.get(base)
            if not cands:
                continue
            if len(cands) == 1:
                out.append((cands[0][0], callee, recv, line))
                continue
            # 오버로드 — line 으로 picker
            picked = None
            if line is not None:
                for fqn, ls, le in cands:
                    if ls <= line <= le:
                        picked = fqn
                        break
            if picked is None:
                picked = cands[0][0]
            out.append((picked, callee, recv, line))
        return out

    @staticmethod
    def _resolve_chain_receivers(parse_results, types) -> None:
        """For `a.b().c()` propagate `b()`'s return type as `c()`'s receiver_type.

        Walks all `calls` relations with `receiver_kind=chain` and looks up
        `(chain_inner_receiver, chain_inner_method)` in a method_return_index
        built from types.methods. Iterates twice to catch 2-level chains
        (`a.b().c().d()` — first pass resolves `c`, second resolves `d`).
        Mutates `r.attributes["receiver_type"]` in place when found.
        """
        # (class_fqn, simple_name) → return_type ; also (simple_class, simple_name) fallback
        full_index: dict[tuple[str, str], str] = {}
        simple_index: dict[tuple[str, str], list[str]] = {}
        for t in types:
            for m in t.methods:
                ret = m.return_type or ""
                if not ret:
                    continue
                base = m.fqn.split("(", 1)[0].split("@line", 1)[0]
                # base = <class_fqn>.<method_name>
                if "." not in base:
                    continue
                class_fqn, method_name = base.rsplit(".", 1)
                full_index[(class_fqn, method_name)] = ret
                simple_class = class_fqn.rsplit(".", 1)[-1]
                simple_index.setdefault((simple_class, method_name), []).append(ret)

        def _lookup(recv: str, method: str) -> str | None:
            if not recv or not method:
                return None
            r = full_index.get((recv, method))
            if r:
                return r
            simple = recv.rsplit(".", 1)[-1]
            cands = simple_index.get((simple, method))
            if cands and len(cands) == 1:
                return cands[0]
            return None

        # Iterate twice to chain 2 levels.
        for _ in range(2):
            for pr in parse_results:
                for r in pr.relations:
                    if r.kind != "calls":
                        continue
                    attrs = r.attributes
                    if not attrs or attrs.get("receiver_kind") != "chain":
                        continue
                    if attrs.get("receiver_type"):
                        continue  # already resolved (e.g. by prior iter)
                    inner_method = attrs.get("chain_inner_method")
                    inner_recv = attrs.get("chain_inner_receiver")
                    resolved = _lookup(str(inner_recv or ""), str(inner_method or ""))
                    if resolved:
                        # Mutate the attribute dict in place (CodeRelation is
                        # frozen, but the attributes dict itself is mutable).
                        attrs["receiver_type"] = resolved.split("<", 1)[0].strip()
                        attrs["chain_resolved"] = True

    @staticmethod
    def _extract_call_seeds(
        parse_results: Iterable[ParseResult],
    ) -> list[tuple[str, str, str, int | None]]:
        """ParseResult.relations 에서 calls 엣지 → CallSite seed 추출.

        seed = (caller_method_fqn, callee_simple_name, callee_receiver_static_type, line)
        receiver static type 은 java_parser 가 attribute 에 박아두면 사용; 없으면 빈 문자열.
        """
        seeds: list[tuple[str, str, str, int | None]] = []
        for pr in parse_results:
            for r in pr.relations:
                if r.kind != "calls":
                    continue
                # source = caller method fqn, target = callee fqn or simple name
                # callee_simple_name 추출
                callee = r.target
                if "." in callee:
                    callee = callee.rsplit(".", 1)[-1]
                receiver = str(r.attributes.get("receiver_type", "")) if r.attributes else ""
                seeds.append((r.source, callee, receiver, r.line))
        return seeds


__all__ = ("RepoImporter", "ImportJob", "find_java_files")
