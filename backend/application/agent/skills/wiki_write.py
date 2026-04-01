"""WikiWriteSkill — generate a new wiki document with LLM + approval flow."""

from __future__ import annotations

import logging
from typing import Any

from backend.core.schemas import ApprovalRequestEvent, WikiWriteAction
from backend.core.session import session_store
from backend.application.agent.skill import SkillResult

logger = logging.getLogger(__name__)

WRITE_SYSTEM_PROMPT = (
    "당신은 사내 Wiki 기술 문서 작성 전문가입니다. "
    "사용자의 요청에 맞는 Wiki 문서를 Markdown 형식으로 작성하세요.\n\n"
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
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import WikiWriteResult

            agent = Agent(
                get_model(),
                output_type=WikiWriteResult,
                system_prompt=WRITE_SYSTEM_PROMPT,
                retries=2,
                defer_model_check=True,
            )
            result = await agent.run(instruction)
            path = result.output.path
            content = result.output.content

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
                content=content,
            )

            return SkillResult(data={
                "path": path,
                "content": content,
                "diff_preview": diff_preview,
                "action_id": action_id,
                "approval_event": approval_event,
            })

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
