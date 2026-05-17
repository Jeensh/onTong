"""BaseAgent — 공통 인터페이스 + streaming event 헬퍼."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from backend.section3.clients.modeling_client import ModelingClient, get_modeling_client
from backend.section3.contracts import StreamEvent, StreamEventType
from backend.section3.llm.openai_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class BaseAgent:
    """모든 task agent / bridge agent 의 공통 부모.

    self.modeling — HTTP wrapper. agent 가 직접 호출.
    self.llm     — OpenAI wrapper. agent 가 LLM 호출.
    """

    name: str = "base"

    def __init__(
        self,
        modeling: ModelingClient | None = None,
        llm: LLMClient | None = None,
    ):
        self.modeling = modeling or get_modeling_client()
        self.llm = llm or get_llm_client()

    # ─── streaming helper ────────────────────────────────────

    @staticmethod
    def event(type_: str, **payload) -> StreamEvent:
        return StreamEvent(type=type_, payload=payload)

    @staticmethod
    def thinking(message: str) -> StreamEvent:
        return StreamEvent(type=StreamEventType.THINKING, payload={"message": message})

    @staticmethod
    def modeling_call(intent: str, parameters: dict) -> StreamEvent:
        return StreamEvent(
            type=StreamEventType.MODELING_CALL,
            payload={"intent": intent, "parameters": parameters},
        )

    @staticmethod
    def modeling_result(response: dict) -> StreamEvent:
        return StreamEvent(
            type=StreamEventType.MODELING_RESULT,
            payload={"response": response},
        )

    @staticmethod
    def layer_scan(layer: str, items: list) -> StreamEvent:
        """ontology 트리의 한 layer 스캔 — 사용자 요구: 'java 의 트리구조 layer 순서대로 스캔'."""
        return StreamEvent(
            type=StreamEventType.LAYER_SCAN,
            payload={"layer": layer, "items": items},
        )

    @staticmethod
    def code_gen(source: str) -> StreamEvent:
        return StreamEvent(
            type=StreamEventType.CODE_GEN,
            payload={"source": source},
        )

    @staticmethod
    def sandbox_run(message: str = "샌드박스 실행 중") -> StreamEvent:
        return StreamEvent(type=StreamEventType.SANDBOX_RUN, payload={"message": message})

    @staticmethod
    def sandbox_result(result: dict | list) -> StreamEvent:
        return StreamEvent(
            type=StreamEventType.SANDBOX_RESULT,
            payload={"result": result},
        )

    @staticmethod
    def final(payload: dict) -> StreamEvent:
        return StreamEvent(type=StreamEventType.FINAL, payload=payload)

    @staticmethod
    def error(message: str, **extra) -> StreamEvent:
        return StreamEvent(
            type=StreamEventType.ERROR,
            payload={"message": message, **extra},
        )

    @staticmethod
    def need_more_info(missing_info: dict) -> StreamEvent:
        """modeling 의 missing_info dict 를 UI 로 forward."""
        return StreamEvent(
            type=StreamEventType.NEED_MORE_INFO,
            payload={"missing_info": missing_info},
        )

    # ─── ontology 응답을 layer 순서로 분해하는 헬퍼 ──────────

    @staticmethod
    def extract_layers(modeling_result: dict) -> list[tuple[str, list]]:
        """modeling result 의 핵심 entity 들을 layer 순서로 분리.

        layer 순서 (Java 코드 의 layer):
            1. Term / Standard / Variable (도메인 layer)
            2. Step / Process (프로세스 layer)
            3. Class / Method (코드 layer)
            4. Table (데이터 layer)
        """
        layers: list[tuple[str, list]] = []
        r = modeling_result or {}

        # process locations (Step)
        if r.get("process_locations"):
            layers.append(("프로세스 (Step)", r["process_locations"]))
        if r.get("direct_impact", {}).get("affected_steps"):
            layers.append(("직접 영향 Step", r["direct_impact"]["affected_steps"]))
        if r.get("indirect_impact", {}).get("downstream_steps"):
            layers.append(("다운스트림 Step", r["indirect_impact"]["downstream_steps"]))

        # source locations (Class/Method)
        if r.get("source_locations"):
            layers.append(("코드 (Class/Method)", r["source_locations"]))
        if r.get("direct_impact", {}).get("methods"):
            layers.append(("영향 메서드", r["direct_impact"]["methods"]))

        # data locations (Table)
        if r.get("data_locations"):
            layers.append(("데이터 (Table)", r["data_locations"]))
        if r.get("data_dependencies"):
            layers.append(("data dependencies", [{"table": t} for t in r["data_dependencies"]]))

        # term
        if r.get("matched_terms"):
            layers.append(("매칭 용어 (Term)", r["matched_terms"]))

        return layers

    # ─── abstract ────────────────────────────────────────────

    async def run(self, *args, **kwargs) -> AsyncIterator[StreamEvent]:
        """각 subclass 가 구현. async generator yield StreamEvent."""
        raise NotImplementedError
