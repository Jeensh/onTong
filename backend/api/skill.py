"""Skill CRUD API — list, get, create, update, delete, match user-facing skills."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import APIRouter, Depends, HTTPException

from backend.core.auth import User, get_current_user
from pydantic import BaseModel as _BaseModel

from backend.core.schemas import SkillContext, SkillCreateRequest, SkillListResponse, SkillMeta


class SkillMoveRequest(_BaseModel):
    new_category: str = ""

logger = logging.getLogger(__name__)

_skill_loader: Any = None  # UserSkillLoader
_skill_matcher: Any = None  # SkillMatcher
_storage: Any = None  # StorageProvider


def init(skill_loader: Any, skill_matcher: Any, storage: Any) -> None:
    global _skill_loader, _skill_matcher, _storage
    _skill_loader = skill_loader
    _skill_matcher = skill_matcher
    _storage = storage


router = APIRouter(prefix="/api/skills", tags=["skills"], dependencies=[Depends(get_current_user)])


def _slugify(title: str) -> str:
    """Convert title to a filename-safe slug."""
    slug = re.sub(r"[^\w가-힣\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"[\s]+", "-", slug.strip())
    return slug or "untitled"


_SKILL_TEMPLATE_INSTRUCTIONS = """\
아래 참조 문서를 바탕으로 사용자의 질문에 답변하세요.

1. (답변에 포함할 내용을 구체적으로 적으세요)
2. (답변 형식을 지정하세요: 표, 목록, 단계별 등)
3. (예외 사항이나 주의점을 포함하세요)
4. (출처를 명시하도록 지시하세요)"""

_SKILL_TEMPLATE_CONTEXT = """\
<!-- 이 스킬이 어떤 상황에서 사용되는지 배경을 적으세요.
     AI가 답변 톤과 깊이를 결정하는 데 참고합니다. -->
(예: 신규 입사자가 온보딩 절차를 모를 때 안내하는 스킬입니다)"""

_SKILL_TEMPLATE_CONSTRAINTS = """\
<!-- 답변에서 지켜야 할 제약 조건을 적으세요. -->
- (예: 사내 정보이므로 외부 URL을 추천하지 마세요)
- (예: 금액 단위는 반드시 원(KRW)으로 표시하세요)"""

_SKILL_TEMPLATE_EXAMPLES = """\
<!-- 사용자가 이 스킬에 물어볼 만한 질문 예시를 적으세요.
     AI가 답변 범위를 파악하는 데 참고합니다. -->
- (예: "출장비 정산 어떻게 해?")
- (예: "해외출장 경비 한도 알려줘")"""

_SKILL_TEMPLATE_ROLE = """\
<!-- AI가 어떤 역할/페르소나로 답변할지 정의하세요. -->
<!-- 톤, 금지 표현, 핵심 목표를 구체적으로 적으면 답변 품질이 올라갑니다. -->
- 톤: (예: 친절하고 환영하는 분위기)
- 금지 표현: (예: "잘 모르겠습니다", "확인해보겠습니다")
- 핵심 목표: (예: 사용자의 불안감을 줄이는 것)"""

_SKILL_TEMPLATE_WORKFLOW = """\
<!-- 답변을 단계별로 진행해야 할 때 워크플로우를 정의하세요. -->
<!-- 각 단계에서 확인할 사항을 명시하면 AI가 순서대로 안내합니다. -->
### 1단계: (단계 이름)
(이 단계에서 할 일을 적으세요)

### 2단계: (단계 이름)
(이 단계에서 할 일을 적으세요)"""

_SKILL_TEMPLATE_CHECKLIST = """\
<!-- 답변에 반드시 포함하거나 절대 언급하지 말아야 할 항목을 적으세요. -->
### 반드시 포함
- (예: 담당 부서 연락처)
- (예: 관련 규정 조항 번호)

### 언급 금지
- (예: 급여 정보)
- (예: 인사 비밀 사항)"""

_SKILL_TEMPLATE_OUTPUT_FORMAT = """\
<!-- AI 답변의 구조를 지정하세요. 형식이 명확할수록 일관된 답변이 나옵니다. -->
답변은 다음 구조로 작성하세요:
1. 📋 요약 (3줄 이내)
2. 📝 상세 내용
3. ❓ 추가 안내 (있을 경우)"""

_SKILL_TEMPLATE_SELF_REGULATION = """\
<!-- AI 답변의 범위와 한도를 정하세요. 과잉 답변을 방지합니다. -->
- 답변 길이: (예: 최대 500자)
- 참조 문서에 없는 내용은 추측하지 마세요
- (예: 1회 답변에 3개 이상의 절차를 나열하지 마세요)"""


def _build_skill_markdown(body: SkillCreateRequest) -> str:
    """Build markdown content from SkillCreateRequest."""
    lines = ["---"]
    lines.append("type: skill")
    if body.description:
        lines.append(f"description: {body.description}")
    if body.trigger:
        lines.append("trigger:")
        for t in body.trigger:
            lines.append(f"  - {t}")
    lines.append(f"icon: {body.icon}")
    lines.append(f"scope: {body.scope}")
    lines.append("enabled: true")
    if body.category:
        lines.append(f"category: {body.category}")
    if body.priority != 5:
        lines.append(f"priority: {body.priority}")
    if body.pinned:
        lines.append("pinned: true")
    lines.append("---")
    lines.append("")
    lines.append(f"# {body.title}")
    lines.append("")

    # Layer 2: Role (optional)
    if body.role:
        lines.append("## 역할")
        lines.append(body.role)
        lines.append("")
    elif not body.instructions:
        lines.append("## 역할")
        lines.append(_SKILL_TEMPLATE_ROLE)
        lines.append("")

    # Layer 3: Instructions — user-provided or template
    lines.append("## 지시사항")
    if body.instructions:
        lines.append(body.instructions)
    else:
        lines.append(_SKILL_TEMPLATE_INSTRUCTIONS)
    lines.append("")

    # Workflow (optional)
    if body.workflow:
        lines.append("## 워크플로우")
        lines.append(body.workflow)
        lines.append("")
    elif not body.instructions:
        lines.append("## 워크플로우")
        lines.append(_SKILL_TEMPLATE_WORKFLOW)
        lines.append("")

    # Context section (template only when no instructions provided)
    if not body.instructions:
        lines.append("## 배경")
        lines.append(_SKILL_TEMPLATE_CONTEXT)
        lines.append("")

        lines.append("## 질문 예시")
        lines.append(_SKILL_TEMPLATE_EXAMPLES)
        lines.append("")

    # Layer 4: Checklist (optional)
    if body.checklist:
        lines.append("## 체크리스트")
        lines.append(body.checklist)
        lines.append("")
    elif not body.instructions:
        lines.append("## 체크리스트")
        lines.append(_SKILL_TEMPLATE_CHECKLIST)
        lines.append("")

    # Layer 5: Output format (optional)
    if body.output_format:
        lines.append("## 출력 형식")
        lines.append(body.output_format)
        lines.append("")
    elif not body.instructions:
        lines.append("## 출력 형식")
        lines.append(_SKILL_TEMPLATE_OUTPUT_FORMAT)
        lines.append("")

    # Layer 6: Self-regulation (optional)
    if body.self_regulation:
        lines.append("## 제한사항")
        lines.append(body.self_regulation)
        lines.append("")
    elif not body.instructions:
        lines.append("## 제한사항")
        lines.append(_SKILL_TEMPLATE_SELF_REGULATION)
        lines.append("")

    # Referenced docs
    lines.append("## 참조 문서")
    if body.referenced_docs:
        for doc in body.referenced_docs:
            display = doc.replace(".md", "") if doc.endswith(".md") else doc
            lines.append(f"- [[{display}]]")
    else:
        lines.append("<!-- 이 스킬이 참고할 위키 문서를 [[문서이름]] 형식으로 추가하세요. -->")
        lines.append("<!-- 참조 문서가 많을수록 AI 답변이 정확해집니다. -->")
        lines.append("- [[문서이름을-여기에]]")
    lines.append("")

    return "\n".join(lines)


@router.get("/")
async def list_skills(user: User = Depends(get_current_user)) -> SkillListResponse:
    """List skills accessible to the current user (including disabled)."""
    if not _skill_loader:
        return SkillListResponse()
    return await _skill_loader.list_skills(user.name, include_disabled=True)


@router.get("/match")
async def match_skill(q: str, user: User = Depends(get_current_user)):
    """Find the best matching skill for a query (for auto-suggestion)."""
    if not _skill_loader or not _skill_matcher:
        return {"match": None}

    result = await _skill_matcher.match(q, user.name, _skill_loader)
    if result:
        skill, confidence = result
        return {
            "match": {
                "skill": skill.model_dump(),
                "confidence": confidence,
            }
        }
    return {"match": None}


@router.patch("/{path:path}/move")
async def move_skill(path: str, body: SkillMoveRequest, user: User = Depends(get_current_user)) -> SkillMeta:
    """Move a skill to a different category by changing its file path."""
    if not _storage or not _skill_loader:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    if not await _storage.exists(path):
        raise HTTPException(status_code=404, detail=f"Skill not found: {path}")

    # Read current content
    wiki_file = await _storage.read(path)
    raw = wiki_file.raw_content or wiki_file.content

    # Update category in frontmatter
    import re as _re
    if _re.search(r"^category:\s*.*$", raw, _re.MULTILINE):
        if body.new_category:
            raw = _re.sub(r"^category:\s*.*$", f"category: {body.new_category}", raw, count=1, flags=_re.MULTILINE)
        else:
            raw = _re.sub(r"^category:\s*.*\n", "", raw, count=1, flags=_re.MULTILINE)
    elif body.new_category:
        raw = raw.replace("\n---\n", f"\ncategory: {body.new_category}\n---\n", 1)

    # Determine new path
    parts = path.split("/")
    # Find the scope base: _skills/ or _skills/@user/
    if "/@" in path:
        # personal: _skills/@user/[category/]slug.md
        idx = path.index("/@")
        at_part = path[idx + 1:].split("/")[0]  # @username
        base = f"_skills/{at_part}"
    else:
        base = "_skills"

    filename = parts[-1]
    if body.new_category:
        new_path = f"{base}/{body.new_category}/{filename}"
    else:
        new_path = f"{base}/{filename}"

    if new_path != path:
        if await _storage.exists(new_path):
            raise HTTPException(status_code=409, detail=f"Target already exists: {new_path}")
        await _write_skill_file(new_path, raw)
        await _storage.delete(path)
    else:
        await _write_skill_file(path, raw)

    _skill_loader.invalidate()

    skill = await _skill_loader.get_skill(new_path)
    if not skill:
        raise HTTPException(status_code=500, detail="Failed to load moved skill")
    return skill


@router.get("/{path:path}/context")
async def get_skill_context(path: str) -> SkillContext:
    """Get structured 6-layer context for a skill."""
    if not _skill_loader:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    skill = await _skill_loader.get_skill(path)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {path}")
    return await _skill_loader.load_skill_context(skill)


@router.get("/{path:path}")
async def get_skill(path: str) -> SkillMeta:
    """Get a single skill by path."""
    if not _skill_loader:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    skill = await _skill_loader.get_skill(path)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {path}")
    return skill


async def _write_skill_file(path: str, content: str) -> None:
    """Write skill file directly, bypassing storage.write() to preserve
    skill-specific frontmatter fields (type, trigger, icon, etc.)."""
    full_path = Path(_storage.wiki_dir) / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
        await f.write(content)


@router.post("/")
async def create_skill(body: SkillCreateRequest, user: User = Depends(get_current_user)) -> SkillMeta:
    """Create a new skill document."""
    if not _storage or not _skill_loader:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    slug = _slugify(body.title)

    if body.scope == "personal":
        base = f"_skills/@{user.name}"
    else:
        base = "_skills"

    if body.category:
        path = f"{base}/{body.category}/{slug}.md"
    else:
        path = f"{base}/{slug}.md"

    # Check if already exists
    if await _storage.exists(path):
        raise HTTPException(status_code=409, detail=f"Skill already exists: {path}")

    content = _build_skill_markdown(body)
    await _write_skill_file(path, content)

    _skill_loader.invalidate()

    skill = await _skill_loader.get_skill(path)
    if not skill:
        raise HTTPException(status_code=500, detail="Failed to parse created skill")
    return skill


@router.put("/{path:path}")
async def update_skill(path: str, body: SkillCreateRequest, user: User = Depends(get_current_user)) -> SkillMeta:
    """Update an existing skill document."""
    if not _storage or not _skill_loader:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    if not await _storage.exists(path):
        raise HTTPException(status_code=404, detail=f"Skill not found: {path}")

    content = _build_skill_markdown(body)
    await _write_skill_file(path, content)

    _skill_loader.invalidate()

    skill = await _skill_loader.get_skill(path)
    if not skill:
        raise HTTPException(status_code=500, detail="Failed to parse updated skill")
    return skill


@router.patch("/{path:path}/toggle")
async def toggle_skill(path: str, user: User = Depends(get_current_user)):
    """Toggle a skill's enabled state.

    Writes raw content directly to avoid storage.write() stripping
    skill-specific frontmatter fields (type, trigger, icon, etc.).
    """
    if not _storage or not _skill_loader:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    wiki_file = await _storage.read(path)
    if not wiki_file:
        raise HTTPException(status_code=404, detail=f"Skill not found: {path}")

    raw = wiki_file.raw_content or wiki_file.content
    # Flip enabled field in frontmatter
    if "enabled: true" in raw:
        updated = raw.replace("enabled: true", "enabled: false", 1)
    elif "enabled: false" in raw:
        updated = raw.replace("enabled: false", "enabled: true", 1)
    else:
        # No enabled field found, insert before closing ---
        updated = raw.replace("\n---\n", "\nenabled: false\n---\n", 1)

    # Write directly to file to preserve all frontmatter fields
    full_path = Path(_storage.wiki_dir) / path
    async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
        await f.write(updated)

    _skill_loader.invalidate()

    skill = await _skill_loader.get_skill(path)
    return {"path": path, "enabled": skill.enabled if skill else False}


@router.delete("/{path:path}")
async def delete_skill(path: str, user: User = Depends(get_current_user)):
    """Delete a skill document."""
    if not _storage or not _skill_loader:
        raise HTTPException(status_code=503, detail="Skill system not initialized")

    if not await _storage.exists(path):
        raise HTTPException(status_code=404, detail=f"Skill not found: {path}")

    await _storage.delete(path)
    _skill_loader.invalidate()

    return {"deleted": path}
