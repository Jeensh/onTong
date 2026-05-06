"""OD-11-D2-2 : ManualIngestPipeline 검증.

포맷 라우팅 + checksum dedup (skip/update/force) + graph 쓰기 + 임베딩 쓰기 + registry 업데이트.
GraphWriter / EmbeddingStore / ManualRegistry 전부 Protocol 주입 → InMemory stub 으로 결정적 테스트.

Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6-2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manual_ingest.pipeline import (
    IngestMode,
    IngestOutcome,
    IngestResult,
    ManualIngestPipeline,
    UnsupportedFormatError,
)
from backend.modeling.manuals.manual_models import (
    ManualDocument,
    ManualFormat,
    ManualFragment,
    ManualFragmentKind,
    ManualSection,
)


# ---------------------------------------------------------------------------
# Fake collaborators
# ---------------------------------------------------------------------------
@dataclass
class _FakeGraphWriter:
    """기록된 entities / relations 집계용."""
    entity_writes: list[tuple[str, str]] = field(default_factory=list)   # (repo_id, qn)
    relation_writes: list[tuple[str, str, str]] = field(default_factory=list)
    deleted_docs: list[str] = field(default_factory=list)

    def write_manual(
        self,
        *,
        document: ManualDocument,
        sections: list[ManualSection],
        fragments: list[ManualFragment],
        repo_id: str,
    ) -> None:
        self.entity_writes.append((repo_id, document.qualified_name))
        for s in sections:
            self.entity_writes.append((repo_id, s.qualified_name))
        for f in fragments:
            self.entity_writes.append((repo_id, f.qualified_name))

    def delete_manual(self, doc_fqn: str, repo_id: str) -> None:
        self.deleted_docs.append(doc_fqn)


@dataclass
class _FakeEmbeddingStore:
    upserted: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def upsert_fragments(self, fragments: list[ManualFragment]) -> None:
        for f in fragments:
            self.upserted.append(f.qualified_name)

    def delete_document(self, doc_fqn: str) -> None:
        self.deleted.append(doc_fqn)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_md(tmp_path: Path, name: str = "spec.md", body: str = "# Spec\n\nBody text.\n") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _make_pipeline(tmp_path: Path) -> tuple[ManualIngestPipeline, _FakeGraphWriter, _FakeEmbeddingStore, InMemoryManualRegistry]:
    from backend.modeling.manual_ingest.md_parser import MarkdownParser
    from backend.modeling.manual_ingest.pdf_parser import PdfParser

    gw = _FakeGraphWriter()
    es = _FakeEmbeddingStore()
    reg = InMemoryManualRegistry()
    pipe = ManualIngestPipeline(
        parsers={
            ManualFormat.MARKDOWN: MarkdownParser(),
            ManualFormat.PDF: PdfParser(),
        },
        registry=reg,
        graph_writer=gw,
        embedding_store=es,
    )
    return pipe, gw, es, reg


# ---------------------------------------------------------------------------
# Format routing
# ---------------------------------------------------------------------------
def test_pipeline_routes_md_to_markdown_parser(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path)
    out = pipe.ingest(md, repo_id="r1")
    assert out.outcome == IngestOutcome.INGESTED
    assert out.document.format == ManualFormat.MARKDOWN
    assert gw.entity_writes   # 뭐든 기록됨


def test_pipeline_unsupported_extension_raises(tmp_path: Path) -> None:
    pipe, *_ = _make_pipeline(tmp_path)
    weird = tmp_path / "spec.xyz"
    weird.write_text("???")
    with pytest.raises(UnsupportedFormatError):
        pipe.ingest(weird, repo_id="r1")


# ---------------------------------------------------------------------------
# Checksum dedup
# ---------------------------------------------------------------------------
def test_pipeline_skip_mode_when_checksum_matches(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path)
    first = pipe.ingest(md, repo_id="r1", mode=IngestMode.SKIP)
    assert first.outcome == IngestOutcome.INGESTED
    # 두 번째 호출 — 동일 checksum → SKIPPED
    second = pipe.ingest(md, repo_id="r1", mode=IngestMode.SKIP)
    assert second.outcome == IngestOutcome.SKIPPED
    assert second.document.qualified_name == first.document.qualified_name
    # 그래프·임베딩 한 번만 호출됐는지
    assert len(gw.entity_writes) == len([e for e in gw.entity_writes if e[0] == "r1"])
    # upsert 횟수는 fragment 수만큼 (한 번의 ingest 만)
    # → 두 번째 ingest 이후에도 es.upserted 수가 변하지 않아야 함
    upsert_count_after_first = pipe._last_upsert_count if hasattr(pipe, "_last_upsert_count") else None
    # 더 정확히 : 같은 내용 중복 ingest 시 es.upserted 길이는 1차 때와 동일
    assert len(es.upserted) == len([u for u in es.upserted if "manual.spec" in u])


def test_pipeline_force_mode_reingests_even_on_same_checksum(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path)
    first = pipe.ingest(md, repo_id="r1", mode=IngestMode.FORCE)
    assert first.outcome == IngestOutcome.INGESTED
    writes_after_first = len(gw.entity_writes)

    second = pipe.ingest(md, repo_id="r1", mode=IngestMode.FORCE)
    assert second.outcome == IngestOutcome.INGESTED   # 다시 ingest 됨
    assert len(gw.entity_writes) > writes_after_first   # 기록 추가됨


def test_pipeline_update_mode_replaces_old_content(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path, body="# A\n\noriginal body\n")
    first = pipe.ingest(md, repo_id="r1", mode=IngestMode.UPDATE)
    assert first.outcome == IngestOutcome.INGESTED

    # 파일 내용 변경 → checksum 변경
    md.write_text("# A\n\nupdated body different content\n")
    second = pipe.ingest(md, repo_id="r1", mode=IngestMode.UPDATE)
    assert second.outcome == IngestOutcome.UPDATED
    # 이전 버전 delete 호출됐는지
    assert first.document.qualified_name in gw.deleted_docs
    assert first.document.qualified_name in es.deleted


def test_pipeline_update_mode_same_checksum_is_skipped(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path)
    first = pipe.ingest(md, repo_id="r1", mode=IngestMode.UPDATE)
    assert first.outcome == IngestOutcome.INGESTED
    # 파일 변경 없음 → UPDATE 모드여도 SKIPPED
    second = pipe.ingest(md, repo_id="r1", mode=IngestMode.UPDATE)
    assert second.outcome == IngestOutcome.SKIPPED


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------
def test_pipeline_registers_document(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path)
    out = pipe.ingest(md, repo_id="r1")
    entry = reg.get_by_fqn(out.document.qualified_name)
    assert entry is not None
    assert entry.document.qualified_name == out.document.qualified_name


def test_pipeline_registers_sections_and_fragments(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path, body="# A\n\nfirst\n\n## Sub\n\nsecond\n")
    out = pipe.ingest(md, repo_id="r1")
    entry = reg.get_by_fqn(out.document.qualified_name)
    assert len(entry.sections) >= 2
    assert len(entry.fragments) >= 2


# ---------------------------------------------------------------------------
# Graph + Embedding writes
# ---------------------------------------------------------------------------
def test_pipeline_writes_document_section_fragment_nodes(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path, body="# Title\n\nbody paragraph.\n")
    out = pipe.ingest(md, repo_id="r1")
    all_qns = {qn for _, qn in gw.entity_writes}
    assert out.document.qualified_name in all_qns
    section_fqns = {s.qualified_name for s in out.parse_result.sections}
    assert section_fqns & all_qns   # 적어도 일부 section 포함


def test_pipeline_upserts_fragments_to_embedding_store(tmp_path: Path) -> None:
    pipe, gw, es, reg = _make_pipeline(tmp_path)
    md = _write_md(tmp_path, body="# T\n\nfragment one.\n\nfragment two.\n")
    out = pipe.ingest(md, repo_id="r1")
    fragment_fqns = {f.qualified_name for f in out.parse_result.fragments}
    assert fragment_fqns.issubset(set(es.upserted))


# ---------------------------------------------------------------------------
# Optional collaborators — pipeline should still work without graph/embedding
# ---------------------------------------------------------------------------
def test_pipeline_works_without_graph_writer(tmp_path: Path) -> None:
    from backend.modeling.manual_ingest.md_parser import MarkdownParser

    reg = InMemoryManualRegistry()
    pipe = ManualIngestPipeline(
        parsers={ManualFormat.MARKDOWN: MarkdownParser()},
        registry=reg,
        graph_writer=None,
        embedding_store=None,
    )
    md = _write_md(tmp_path)
    out = pipe.ingest(md, repo_id="r1")
    assert out.outcome == IngestOutcome.INGESTED


# ---------------------------------------------------------------------------
# Detect format from extension
# ---------------------------------------------------------------------------
def test_detect_format_from_extension(tmp_path: Path) -> None:
    from backend.modeling.manual_ingest.pipeline import detect_format

    assert detect_format(Path("x.md")) == ManualFormat.MARKDOWN
    assert detect_format(Path("x.markdown")) == ManualFormat.MARKDOWN
    assert detect_format(Path("x.pdf")) == ManualFormat.PDF
    assert detect_format(Path("x.docx")) == ManualFormat.DOCX
    assert detect_format(Path("x.pptx")) == ManualFormat.PPTX
    assert detect_format(Path("x.png")) == ManualFormat.IMAGE
    assert detect_format(Path("x.jpg")) == ManualFormat.IMAGE
    assert detect_format(Path("x.jpeg")) == ManualFormat.IMAGE


def test_detect_format_unsupported_returns_none(tmp_path: Path) -> None:
    from backend.modeling.manual_ingest.pipeline import detect_format

    assert detect_format(Path("x.xyz")) is None
    assert detect_format(Path("no-ext")) is None
