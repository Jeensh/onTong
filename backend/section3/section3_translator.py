"""Sprint 5 — Section 3 전용 Java→Python translator (sim_v2 JavaToPythonTranslator 의 subclass).

transpiler-bridge.md §3 옵션 B 의 구현. sim_v2 의 71-handler 모두 상속하면서
Section 3 도메인 특화 idiom rewrite 만 patch 가능한 extension point 를 제공.

현재 sim_v2 의 W75 idiom rewriter 가 50+ Java idiom (String/Collection/Optional/
Math/Objects) 을 이미 자동 처리하므로, 본 subclass 는 기본적으로 no-op 으로
동작한다. 필요 시 `_IDIOM_REWRITES` dict 에 (receiver_type, method_name) → rewrite_fn
형태로 추가하여 sim_v2 보다 우선 적용 가능.

deprecation 안내:
- `backend/section3/transpiler.py` (이전 자체 transpiler) 는 legacy composer
  경로에서만 사용되며, ontology.db 가 비어 있어 사실상 비활성. sim_v2 직통
  경로 (`_run_via_simv2`) 가 본 모듈을 통해 사용된다.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# (receiver_type, method_name) → callable(receiver_src, arg_strs) -> python_expr
IdiomRewriter = Callable[[str, list[str]], str]


class Section3Translator:
    """sim_v2 JavaToPythonTranslator 의 thin wrapper.

    런타임에 sim_v2 가 import 가능하면 그 클래스를 subclass 하여 사용. 불가능
    하면 graceful skip (테스트 환경 등).
    """

    _IDIOM_REWRITES: dict[tuple[str, str], IdiomRewriter] = {
        # (receiver_type, method_name) → fn(receiver_src, arg_strs) -> python expr
        # 예시 — sim_v2 W75 가 커버 안 하는 특수 도메인 idiom 만 여기에.
        # 현재 비어 있음 — sim_v2 W75 의 50+ idiom 으로 충분.
    }

    def __new__(cls, *args: Any, **kwargs: Any):
        # 동적 base — sim_v2 가 있으면 그 subclass 로, 없으면 stub
        try:
            from backend.sim_v2.core.synthesizer.java_translator import (
                JavaToPythonTranslator,
            )
        except ImportError as e:
            logger.warning("sim_v2 translator 미가용 → Section3Translator inert: %s", e)
            return None

        if cls is Section3Translator:
            # 동적으로 sim_v2 base 와 합성한 subclass 를 생성
            Combined = type(
                "Section3TranslatorImpl",
                (cls, JavaToPythonTranslator),
                {},
            )
            inst = object.__new__(Combined)
            return inst
        return object.__new__(cls)

    def _translate_method_invocation(self, node, *, indent: int) -> str:
        # Section 3 idiom 이 있으면 먼저 적용
        rewrites = type(self)._IDIOM_REWRITES
        if rewrites:
            obj_node = node.child_by_field_name("object")
            name_node = node.child_by_field_name("name")
            args_node = node.child_by_field_name("arguments")
            method_name = self._text(name_node) if name_node else ""
            if obj_node is not None and method_name:
                receiver_type = self._infer_type(obj_node) or ""
                key = (receiver_type, method_name)
                if key in rewrites:
                    receiver_src = self._dispatch(obj_node, indent=0)
                    arg_strs = []
                    if args_node:
                        for ch in args_node.named_children:
                            arg_strs.append(self._dispatch(ch, indent=0))
                    return rewrites[key](receiver_src, arg_strs)

        # fallback — sim_v2 base 가 처리
        return super()._translate_method_invocation(node, indent=indent)


def make_translator() -> Optional[Any]:
    """현재 환경에서 사용 가능한 translator 인스턴스 반환. sim_v2 없으면 None."""
    return Section3Translator()


__all__ = ["Section3Translator", "make_translator", "IdiomRewriter"]
