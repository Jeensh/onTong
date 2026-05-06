"""Perspective schema (R4-T2.2, 안건 2 B 결정).

Bloom Perspective 차용 — 그래프 view 의 named bundle.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


GraphMode = Literal["neighborhood", "path", "cluster"]


class PerspectiveSpec(BaseModel):
    """그래프 view 의 실제 spec — Perspective.spec_json 에 직렬화.

    1차에 strict 한 Pydantic 으로 시작. 새 facet 추가 시 마이그레이션 필요. 향후
    유연성 필요하면 extra='allow' 로 완화 가능.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Mode + 핵심 layout 옵션
    mode: GraphMode = "neighborhood"
    n_max: int = Field(default=60, ge=10, le=600)
    focus_fqn: str | None = None
    target_fqn: str | None = None         # path mode 용
    hops: int | None = None                # 옛 호환

    # Visible kinds (R4-T3.1 — domain 추가, 5-kind)
    visible_kinds: list[str] = Field(
        default_factory=lambda: ["term", "code_type", "action", "domain"],
    )
    # Visible edge kinds (R4-T3.1 — contains 추가)
    visible_edge_kinds: list[str] = Field(
        default_factory=lambda: [
            "extends", "implements", "composition",
            "type_realization_primary", "type_realization_partial",
            "realization", "contains",
        ],
    )

    # R4-T3.3 — Domain compound (패키지 box nesting)
    compound: bool = False

    # Filter — facet 별 (role / verification / domain / package 등)
    # 예: {"role": ["domain"], "verification_min": "draft", "package_prefix": "feature.sd"}
    filter: dict[str, Any] = Field(default_factory=dict)

    # Lens — 어떤 facet 으로 색 입힐지 (verification heat / confirmed bool / package color)
    lens: str | None = None

    @model_validator(mode="after")
    def _path_mode_needs_target(self) -> "PerspectiveSpec":
        if self.mode == "path" and self.focus_fqn and not self.target_fqn:
            # 경로 mode 인데 target 없음 — UI 가 두 번째 검색 기다리는 중. 허용.
            pass
        return self


class Perspective(BaseModel):
    """저장된 그래프 view. backend 1급 entity (안건 2 B).

    1차에 read-only public — 같은 repo 의 누구나 fetch 가능. owner_id 는
    ACL 도입 prep.
    """
    model_config = ConfigDict(extra="forbid")

    id: int | None = None                  # autoincrement, 신규 생성 시 None
    name: str = Field(min_length=1, max_length=200)
    repo_id: str = Field(min_length=1)
    description: str = ""
    spec: PerspectiveSpec
    owner_id: str | None = None            # 1차 None OK, 향후 ACL 시 user fqn
    created_at: datetime | None = None
    updated_at: datetime | None = None
