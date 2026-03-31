"""Main Router — 2-tier intent classification (keyword → LLM fallback)."""

from __future__ import annotations

import re
import logging

import litellm

from backend.core.config import settings
from backend.core.schemas import RouterDecision

logger = logging.getLogger(__name__)

# Tier 1: keyword/pattern matching rules
KEYWORD_RULES: list[tuple[str, str, float]] = [
    # (regex_pattern, agent_name, confidence)
    # --- SIMULATION ---
    (r"(시뮬|예측|최적화|파라미터|테스트.*결과)", "SIMULATION", 0.85),
    (r"(모델링|시뮬레이션|시나리오|what.?if)", "SIMULATION", 0.80),
    # --- DEBUG_TRACE ---
    (r"(추적|디버그|원인|장애.*분석|git|커밋|의존성|트레이스)", "DEBUG_TRACE", 0.85),
    (r"(왜.*사라|왜.*삭제|왜.*실패|root.?cause)", "DEBUG_TRACE", 0.85),
    (r"(로그|에러.*추적|스택.*트레이스|버그|rollback|롤백)", "DEBUG_TRACE", 0.80),
    (r"(원인.*분석|장애.*원인|문제.*원인|실패.*원인)", "DEBUG_TRACE", 0.80),
    # --- WIKI_QA (high confidence) ---
    (r"(wiki|문서|위키|지식|나무).*(검색|찾|조회|알려|뭐|어떻게|설명)", "WIKI_QA", 0.9),
    (r"(검색|찾|조회).*(wiki|문서|위키)", "WIKI_QA", 0.9),
    (r"(장애|대응|절차|규칙|룰|정책|가이드)", "WIKI_QA", 0.8),
    # --- WIKI_QA (general search / question patterns) ---
    (r"(찾아|검색해|조회해|알려|알아봐|찾을|검색할)", "WIKI_QA", 0.75),
    (r"(누가|누구|어떤\s*사람|담당자|인원|사람.*찾)", "WIKI_QA", 0.75),
    (r"(어떻게|어디|무엇|뭐가|뭘|뭐야|알고\s*싶|궁금)", "WIKI_QA", 0.7),
    (r"(진행|현황|상태|정보|내용|방법|절차)", "WIKI_QA", 0.65),
    (r".*(에\s*대해|관해|관련|대한).*", "WIKI_QA", 0.65),
    # --- WIKI_QA (corporate / domain terms) ---
    (r"(회의|미팅|일정|스케줄|공지|안내|보고|보고서)", "WIKI_QA", 0.70),
    (r"(매뉴얼|메뉴얼|SOP|표준|기준|규정|규격)", "WIKI_QA", 0.75),
    (r"(교육|OJT|연수|훈련|온보딩)", "WIKI_QA", 0.70),
    (r"(조직|부서|팀|그룹|센터|본부|사업부)", "WIKI_QA", 0.65),
    (r"(연락처|전화|이메일|메일|담당)", "WIKI_QA", 0.70),
    (r"(시스템|서비스|플랫폼|솔루션|인프라|서버)", "WIKI_QA", 0.60),
    (r"(프로젝트|과제|업무|작업|태스크)", "WIKI_QA", 0.60),
    (r"(MES|ERP|SCM|CRM|PLM|DG\d{3})", "WIKI_QA", 0.70),
    (r"(안녕|하이|헬로|도움|도와)", "WIKI_QA", 0.55),
    # --- WIKI_QA (catch-all: any Korean text ≥ 2 chars) ---
    (r"[가-힣]{2,}", "WIKI_QA", 0.50),
]


class MainRouter:
    async def route(self, message: str) -> RouterDecision:
        """Route user message to the appropriate agent."""
        # Tier 1: fast keyword matching
        for pattern, agent, confidence in KEYWORD_RULES:
            if re.search(pattern, message, re.IGNORECASE):
                logger.info(f"Keyword match: '{pattern}' → {agent}")
                return RouterDecision(
                    agent=agent,
                    confidence=confidence,
                    reasoning=f"keyword_match: {pattern}",
                )

        # Tier 2: LLM fallback for ambiguous input
        return await self._llm_classify(message)

    async def _llm_classify(self, message: str) -> RouterDecision:
        """Use LLM to classify intent when keywords don't match."""
        try:
            response = await litellm.acompletion(
                model=settings.litellm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an intent classifier for a corporate wiki knowledge system.\n"
                            "Classify the user message into one of:\n"
                            "- WIKI_QA — ANY question that could be answered by searching wiki documents "
                            "(knowledge lookups, people search, procedures, policies, general info queries)\n"
                            "- SIMULATION — prediction, optimization, parameter tuning, simulation requests\n"
                            "- DEBUG_TRACE — debugging, tracing, root cause analysis, git/commit investigation\n\n"
                            "DEFAULT: If the query does not clearly fit SIMULATION or DEBUG_TRACE, "
                            "classify it as WIKI_QA. Most user queries are knowledge questions.\n"
                            "Respond with ONLY the agent name, nothing else."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                max_tokens=20,
                temperature=0,
            )
            agent_name = response.choices[0].message.content.strip().upper()

            valid = {"WIKI_QA", "SIMULATION", "DEBUG_TRACE"}
            if agent_name not in valid:
                # Default to WIKI_QA for any unrecognized/UNKNOWN intent
                agent_name = "WIKI_QA"

            return RouterDecision(
                agent=agent_name,
                confidence=0.7,
                reasoning="llm_classification",
            )
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return RouterDecision(
                agent="WIKI_QA",
                confidence=0.5,
                reasoning=f"llm_fallback_error: {e}",
            )


router = MainRouter()
