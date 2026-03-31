"""Tests for Skill CRUD API — create, read, update, delete, toggle, move, match, context.

Uses FastAPI TestClient with mocked storage to run isolated tests
without needing a live server.

Usage:
    cd /path/to/onTong
    source venv/bin/activate
    pytest tests/test_skill_api.py -v
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import skill as skill_api
from backend.application.skill.skill_loader import UserSkillLoader
from backend.application.skill.skill_matcher import SkillMatcher
from backend.core.auth import User, get_current_user


# ---------------------------------------------------------------------------
# Fake storage backed by a temp directory
# ---------------------------------------------------------------------------

class FakeWikiFile:
    def __init__(self, path: str, raw_content: str, title: str = ""):
        self.path = path
        self.raw_content = raw_content
        self.content = raw_content
        self.title = title or path.split("/")[-1].replace(".md", "")


class TempDirStorage:
    """Real filesystem storage backed by a temp directory."""

    def __init__(self, wiki_dir: str):
        self.wiki_dir = wiki_dir

    async def list_file_paths(self) -> list[str]:
        result = []
        base = Path(self.wiki_dir)
        for p in base.rglob("*.md"):
            result.append(str(p.relative_to(base)))
        return result

    async def read(self, path: str) -> FakeWikiFile | None:
        full = Path(self.wiki_dir) / path
        if not full.exists():
            return None
        content = full.read_text(encoding="utf-8")
        return FakeWikiFile(path=path, raw_content=content)

    async def exists(self, path: str) -> bool:
        return (Path(self.wiki_dir) / path).exists()

    async def delete(self, path: str) -> None:
        full = Path(self.wiki_dir) / path
        if full.exists():
            full.unlink()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wiki_dir():
    d = tempfile.mkdtemp(prefix="ontong_skill_test_")
    # Create _skills/ directory
    (Path(d) / "_skills" / "HR").mkdir(parents=True)
    (Path(d) / "_skills" / "Finance").mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def storage(wiki_dir):
    return TempDirStorage(wiki_dir)


@pytest.fixture
def app(storage):
    """Create a minimal FastAPI app with skill routes."""
    test_app = FastAPI()

    # Override auth to return a test user
    test_user = User(id="test", name="tester", roles=["admin"])
    test_app.dependency_overrides[get_current_user] = lambda: test_user

    loader = UserSkillLoader(storage)
    matcher = SkillMatcher()
    skill_api.init(loader, matcher, storage)

    test_app.include_router(skill_api.router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def seed_skill(wiki_dir):
    """Write a seed skill file for read/update/delete tests."""
    content = (
        "---\n"
        "type: skill\n"
        "description: 온보딩 안내 스킬\n"
        "trigger:\n"
        "  - 온보딩\n"
        "  - 신규입사자\n"
        "icon: 🎯\n"
        "scope: shared\n"
        "enabled: true\n"
        "---\n\n"
        "# 신규입사자 온보딩\n\n"
        "## 역할\n친절한 HR 담당자\n\n"
        "## 지시사항\n온보딩 절차를 안내합니다.\n\n"
        "## 참조 문서\n- [[온보딩-가이드]]\n"
    )
    path = Path(wiki_dir) / "_skills" / "HR" / "onboarding.md"
    path.write_text(content, encoding="utf-8")
    return "_skills/HR/onboarding.md"


# ---------------------------------------------------------------------------
# Tests: Create
# ---------------------------------------------------------------------------

class TestCreateSkill:
    def test_create_basic(self, client):
        resp = client.post("/api/skills/", json={
            "title": "출장비 정산",
            "description": "출장비 정산 안내",
            "trigger": ["출장비", "경비"],
            "scope": "shared",
            "category": "Finance",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "출장비 정산"
        assert "Finance" in data["path"]
        assert data["enabled"] is True

    def test_create_duplicate(self, client):
        body = {
            "title": "중복 테스트",
            "scope": "shared",
            "category": "HR",
        }
        resp1 = client.post("/api/skills/", json=body)
        assert resp1.status_code == 200

        resp2 = client.post("/api/skills/", json=body)
        assert resp2.status_code == 409

    def test_create_with_6layer(self, client):
        resp = client.post("/api/skills/", json={
            "title": "6레이어 스킬",
            "trigger": ["테스트"],
            "scope": "shared",
            "instructions": "이것은 지시사항",
            "role": "전문 상담사",
            "workflow": "### 1단계\n확인",
            "checklist": "- 필수 항목",
            "output_format": "1. 요약",
            "self_regulation": "500자 이내",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "6레이어 스킬"


# ---------------------------------------------------------------------------
# Tests: Read
# ---------------------------------------------------------------------------

class TestReadSkill:
    def test_get_existing(self, client, seed_skill):
        resp = client.get(f"/api/skills/{seed_skill}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "신규입사자 온보딩"
        assert "온보딩" in data["trigger"]

    def test_get_not_found(self, client):
        resp = client.get("/api/skills/_skills/nonexistent.md")
        assert resp.status_code == 404

    def test_list_skills(self, client, seed_skill):
        resp = client.get("/api/skills/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["system"]) >= 1
        titles = {s["title"] for s in data["system"]}
        assert "신규입사자 온보딩" in titles


# ---------------------------------------------------------------------------
# Tests: Update
# ---------------------------------------------------------------------------

class TestUpdateSkill:
    def test_update(self, client, seed_skill):
        resp = client.put(f"/api/skills/{seed_skill}", json={
            "title": "업데이트된 온보딩",
            "description": "수정됨",
            "trigger": ["온보딩", "입사"],
            "scope": "shared",
            "instructions": "수정된 지시사항",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "업데이트된 온보딩"

    def test_update_not_found(self, client):
        resp = client.put("/api/skills/_skills/ghost.md", json={
            "title": "없는 스킬",
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Toggle
# ---------------------------------------------------------------------------

class TestToggleSkill:
    def test_toggle_disable(self, client, seed_skill):
        resp = client.patch(f"/api/skills/{seed_skill}/toggle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False

    def test_toggle_reenable(self, client, seed_skill):
        # Disable
        client.patch(f"/api/skills/{seed_skill}/toggle")
        # Re-enable
        resp = client.patch(f"/api/skills/{seed_skill}/toggle")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_toggle_not_found(self, client):
        resp = client.patch("/api/skills/_skills/ghost.md/toggle")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Delete
# ---------------------------------------------------------------------------

class TestDeleteSkill:
    def test_delete(self, client, seed_skill):
        resp = client.delete(f"/api/skills/{seed_skill}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == seed_skill

        # Verify gone
        resp2 = client.get(f"/api/skills/{seed_skill}")
        assert resp2.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/skills/_skills/ghost.md")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Move
# ---------------------------------------------------------------------------

class TestMoveSkill:
    def test_move_to_new_category(self, client, seed_skill):
        resp = client.patch(
            f"/api/skills/{seed_skill}/move",
            json={"new_category": "General"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "General" in data["path"]
        assert data["category"] == "General"

    def test_move_to_root(self, client, seed_skill):
        resp = client.patch(
            f"/api/skills/{seed_skill}/move",
            json={"new_category": ""},
        )
        assert resp.status_code == 200
        # Should be at _skills/onboarding.md (no subfolder)
        assert resp.json()["path"] == "_skills/onboarding.md"

    def test_move_not_found(self, client):
        resp = client.patch(
            "/api/skills/_skills/ghost.md/move",
            json={"new_category": "HR"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Match
# ---------------------------------------------------------------------------

class TestMatchSkill:
    def test_match_found(self, client, seed_skill):
        resp = client.get("/api/skills/match?q=온보딩 절차 알려줘")
        assert resp.status_code == 200
        data = resp.json()
        assert data["match"] is not None
        assert data["match"]["skill"]["title"] == "신규입사자 온보딩"
        assert data["match"]["confidence"] >= 0.5

    def test_match_not_found(self, client, seed_skill):
        resp = client.get("/api/skills/match?q=완전히 관계없는 질문")
        assert resp.status_code == 200
        assert resp.json()["match"] is None


# ---------------------------------------------------------------------------
# Tests: Context (6-layer)
# ---------------------------------------------------------------------------

class TestSkillContext:
    def test_get_context(self, client, seed_skill):
        resp = client.get(f"/api/skills/{seed_skill}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert "온보딩" in data["instructions"]
        assert "HR 담당자" in data["role"]

    def test_context_not_found(self, client):
        resp = client.get("/api/skills/_skills/ghost.md/context")
        assert resp.status_code == 404
