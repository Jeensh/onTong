"""AG-3-1: Session JSONL persistence — unit tests.

Uses importlib.reload to avoid cross-test module cache issues.
"""

import importlib
import json
import sys
import tempfile
import types
from pathlib import Path


def _make_store(tmpdir):
    """Create a SessionStore with fresh module import."""
    # Ensure stubs exist
    for mod_name in [
        "chromadb", "chromadb.config", "pydantic_ai", "pydantic_ai.models",
        "pydantic_ai.models.openai", "pydantic_settings",
        "litellm", "httpx",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)
    _ps = sys.modules["pydantic_settings"]
    if not hasattr(_ps, "BaseSettings"):
        _ps.BaseSettings = type("BaseSettings", (), {"model_config": {}})

    # Reload to get fresh class definitions
    import backend.core.session as _mod
    importlib.reload(_mod)
    return _mod.SessionStore(data_dir=tmpdir)


def test_append_message_persists_to_jsonl():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        store.append_message("sess-1", {"role": "user", "content": "hello"})
        store.append_message("sess-1", {"role": "assistant", "content": "hi there"})

        path = Path(tmpdir) / "sess-1.jsonl"
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["role"] == "user"
        assert json.loads(lines[1])["content"] == "hi there"


def test_restore_sessions_on_startup():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "restored-sess.jsonl"
        records = [
            {"ts": "2026-01-01T00:00:00", "role": "user", "content": "question"},
            {"ts": "2026-01-01T00:00:01", "role": "assistant", "content": "answer"},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        store = _make_store(tmpdir)
        session = store.get_or_create_session("restored-sess")
        assert len(session.messages) == 2
        assert session.messages[0]["content"] == "question"


def test_corrupt_lines_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "corrupt-sess.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"ts":"t","role":"user","content":"ok"}\n')
            f.write("this is not json\n")
            f.write('{"ts":"t","role":"assistant","content":"fine"}\n')

        store = _make_store(tmpdir)
        session = store.get_or_create_session("corrupt-sess")
        assert len(session.messages) == 2


def test_multiple_sessions_independent():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        store.append_message("a", {"role": "user", "content": "msg-a"})
        store.append_message("b", {"role": "user", "content": "msg-b"})
        assert len(store.get_or_create_session("a").messages) == 1
        assert len(store.get_or_create_session("b").messages) == 1


def test_get_or_create_empty_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        session = store.get_or_create_session("brand-new")
        assert session.messages == []


def test_session_id_sanitized():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _make_store(tmpdir)
        store.append_message("../evil", {"role": "user", "content": "bad"})
        assert not (Path(tmpdir).parent / "evil.jsonl").exists()
        assert (Path(tmpdir) / "evil.jsonl").exists()
