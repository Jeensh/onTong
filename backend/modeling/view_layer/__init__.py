"""View Layer (R4-T2.2) — 사용자 정의 그래프 view (Perspective).

Bloom Perspective 차용. visible kinds + lens + filter + layout + saved focus 묶음을
backend 1급 entity 로 저장. 1차 read-only public, owner_id 만 future ACL prep.
"""
from backend.modeling.view_layer.schema import Perspective, PerspectiveSpec

__all__ = ("Perspective", "PerspectiveSpec")
