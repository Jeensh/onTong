"""WikiWriteSkill — generate a new wiki document with LLM + approval flow."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

from backend.core.config import settings
from backend.core.schemas import ApprovalRequestEvent, WikiWriteAction
from backend.core.session import session_store
from backend.application.agent.skill import SkillResult

logger = logging.getLogger(__name__)

WRITE_SYSTEM_PROMPT = (
    "당신은 사내 Wiki 기술 문서 작성 전문가입니다. "
    "사용자의 요청에 맞는 Wiki 문서를 Markdown 형식으로 작성하세요.\n\n"
    "응답은 반드시 다음 JSON 형식으로 해주세요 (마크다운 펜스 없이):\n"
    '{"path": "파일명.md", "content": "# 제목\\n\\n문서 내용..."}\n\n'
    "path는 적절한 파일명(한글 가능, .md 확장자), "
    "content는 완전한 Markdown 문서입니다."
)


class WikiWriteSkill:
    name = "wiki_write"
    description = "새 Wiki 문서를 생성합니다 (사용자 승인 필요)"

    async def execute(self, ctx: Any, *, instruction: str = "") -> SkillResult:
        if not instruction:
            return SkillResult(data=None, success=False, error="instruction required")

        try:
            response = await litellm.acompletion(
                model=settings.litellm_model,
                messages=[
                    {"role": "system", "content": WRITE_SYSTEM_PROMPT},
                    {"role": "user", "content": instruction},
                ],
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(raw)
            path = data.get("path", "new-document.md")
            content = data.get("content", "")

            if not content:
                return SkillResult(data=None, success=False, error="LLM produced empty content")

            # Create preview
            preview_lines = content.split("\n")[:20]
            diff_preview = "\n".join(preview_lines)
            if len(content.split("\n")) > 20:
                diff_preview += "\n... (truncated)"

            # Store pending action
            action = WikiWriteAction(path=path, content=content, diff_preview=diff_preview)
            action_id = session_store.add_pending_action(ctx.request.session_id, action)

            # Build approval event
            approval_event = ApprovalRequestEvent(
                action_id=action_id,
                action_type="wiki_write",
                path=path,
                diff_preview=diff_preview,
            )

            return SkillResult(data={
                "path": path,
                "content": content,
                "diff_preview": diff_preview,
                "action_id": action_id,
                "approval_event": approval_event,
            })

        except json.JSONDecodeError:
            return SkillResult(data=None, success=False, error="LLM response JSON parse failed")
        except Exception as e:
            logger.error(f"wiki_write failed: {e}")
            return SkillResult(data=None, success=False, error=str(e))

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instruction": {"type": "string", "description": "문서 작성 요청 내용"},
                    },
                    "required": ["instruction"],
                },
            },
        }
