"""WikiEditSkill — edit an existing wiki document with LLM + approval flow."""

from __future__ import annotations

import logging
from typing import Any

from backend.core.schemas import ApprovalRequestEvent, WikiEditAction
from backend.core.session import session_store
from backend.application.agent.skill import SkillResult
from backend.application.agent.skills.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

EDIT_SYSTEM_PROMPT = load_prompt("wiki_edit")


class WikiEditSkill:
    name = "wiki_edit"
    description = "기존 Wiki 문서를 수정합니다 (사용자 승인 필요)"

    async def execute(
        self,
        ctx: Any,
        *,
        instruction: str = "",
        target_path: str = "",
        history: list[dict] | None = None,
    ) -> SkillResult:
        if not instruction:
            return SkillResult(data=None, success=False, error="instruction required")

        best_file_path = target_path

        try:
            # If no explicit target, try attached files first
            if not best_file_path and ctx.request.attached_files:
                best_file_path = ctx.request.attached_files[0]

            # If still no target, search for it
            if not best_file_path:
                found = await self._find_target_document(ctx, instruction)
                if not found:
                    return SkillResult(
                        data=None, success=False,
                        error="수정할 대상 문서를 찾지 못했습니다. 📎 버튼으로 수정할 파일을 첨부해주세요."
                    )
                best_file_path = found

            # Read original document
            storage = ctx.storage
            if not storage:
                return SkillResult(data=None, success=False, error="storage not available")

            wiki_file = await storage.read(best_file_path)
            if not wiki_file:
                return SkillResult(
                    data=None, success=False,
                    error=f"**{best_file_path}** 문서를 찾을 수 없습니다."
                )

            original_content = wiki_file.raw_content or wiki_file.content

            # Build conversation context
            history_text = ""
            if history:
                from backend.application.agent.rag_agent import build_history_window
                recent = build_history_window(history, max_tokens=1500)
                history_text = "\n".join(
                    f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content'][:200]}"
                    for h in recent
                )
                history_text = f"\n\n## 대화 히스토리\n{history_text}"

            # LLM generates edited version via Pydantic AI
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import WikiEditResult

            agent = Agent(
                get_model(),
                output_type=WikiEditResult,
                system_prompt=EDIT_SYSTEM_PROMPT,
                retries=2,
                defer_model_check=True,
            )
            result = await agent.run(
                f"## 수정 대상 문서: {best_file_path}\n\n"
                f"## 현재 문서 내용\n```\n{original_content}\n```\n"
                f"{history_text}\n\n"
                f"## 수정 요청\n{instruction}"
            )
            new_content = result.output.content
            summary = result.output.summary

            if not new_content:
                return SkillResult(
                    data=None, success=False,
                    error="문서 수정 내용을 생성하지 못했습니다."
                )

            # Create diff preview
            preview_lines = new_content.split("\n")[:25]
            diff_preview = "\n".join(preview_lines)
            if len(new_content.split("\n")) > 25:
                diff_preview += "\n... (truncated)"

            # Store pending action
            action = WikiEditAction(path=best_file_path, content=new_content, diff_preview=diff_preview)
            action_id = session_store.add_pending_action(ctx.request.session_id, action)

            approval_event = ApprovalRequestEvent(
                action_id=action_id,
                action_type="wiki_edit",
                path=best_file_path,
                diff_preview=diff_preview,
                content=new_content,
                original_content=original_content,
            )

            return SkillResult(data={
                "path": best_file_path,
                "content": new_content,
                "original_content": original_content,
                "summary": summary,
                "diff_preview": diff_preview,
                "action_id": action_id,
                "approval_event": approval_event,
            })

        except Exception as e:
            logger.error(f"wiki_edit failed: {e}")
            return SkillResult(data=None, success=False, error=str(e))

    async def _find_target_document(self, ctx: Any, query: str) -> str | None:
        """Search for the most relevant document to edit."""
        chroma = ctx.chroma
        if not chroma:
            return None

        results = chroma.query(query, n_results=8)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            return None

        # Deduplicate by file_path
        seen_files: dict[str, str] = {}
        for meta, doc in zip(metadatas, documents):
            fp = meta.get("file_path", "")
            if fp and fp not in seen_files:
                seen_files[fp] = doc[:200]

        if not seen_files:
            return None

        # Use Pydantic AI to pick the best target
        file_list = "\n".join(f"- {fp}: {preview[:100]}..." for fp, preview in seen_files.items())

        try:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model

            pick_agent = Agent(
                get_model(), output_type=str,
                system_prompt=(
                    "사용자가 Wiki 문서를 수정하려고 합니다. "
                    "아래 후보 문서 목록에서 사용자의 수정 요청에 가장 적합한 문서를 선택하세요.\n\n"
                    "응답은 파일명만 한 줄로 (예: 직원정보-마케팅DX그룹.md)"
                ),
                defer_model_check=True,
            )
            result = await pick_agent.run(f"수정 요청: {query}\n\n후보 문서:\n{file_list}")
            picked = result.output.strip().replace("`", "").strip()
            for fp in seen_files:
                if fp in picked or picked in fp:
                    return fp
        except Exception as e:
            logger.warning(f"Target document selection failed: {e}")

        # Fallback: first result
        return next(iter(seen_files), None)

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instruction": {"type": "string", "description": "수정 요청 내용"},
                        "target_path": {"type": "string", "description": "수정 대상 문서 경로 (optional)"},
                    },
                    "required": ["instruction"],
                },
            },
        }
