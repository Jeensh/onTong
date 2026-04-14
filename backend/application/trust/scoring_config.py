"""Centralized scoring configuration for the Document Trust System.

ALL thresholds, weights, and formulas are defined here.
No scoring magic numbers should exist outside this file.

Usage:
    from backend.application.trust.scoring_config import SCORING

    SCORING.confidence.weights.freshness  → 30
    SCORING.related.min_similarity        → 0.7
    SCORING.related.composite_formula     → "0.6 * similarity + 0.4 * (confidence / 100)"

Tuning guide:
    - Adjust weights to change what matters most
    - Adjust thresholds to control sensitivity
    - All changes take effect on next request (no restart needed for env overrides)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, str(default)))


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


# ── Confidence Score ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ConfidenceWeights:
    """How much each signal contributes to the confidence score (must sum to 100)."""
    freshness: int = 25       # how recently updated
    status: int = 25          # document lifecycle stage
    metadata: int = 15        # completeness of domain/process/tags/author
    backlinks: int = 10       # how many other docs reference this one
    owner_activity: int = 10  # is the author still active
    user_feedback: int = 15   # verified vs needs_update ratio from user feedback


@dataclass(frozen=True)
class ConfidenceThresholds:
    """Tier boundaries and decay parameters."""
    high_min: int = 70          # score >= 70 → "high" tier
    medium_min: int = 40        # score >= 40 → "medium" tier (below → "low")
    stale_months: int = 12      # months since update to flag as stale
    freshness_decay_months: int = 24  # linear decay period (0 months=100, N months=0)


@dataclass(frozen=True)
class StatusScores:
    """Score each document status contributes to confidence."""
    deprecated: float = 0.0
    draft: float = 40.0
    approved: float = 100.0


@dataclass(frozen=True)
class ConfidenceConfig:
    weights: ConfidenceWeights = field(default_factory=ConfidenceWeights)
    thresholds: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    status_scores: StatusScores = field(default_factory=StatusScores)


# ── Related Documents ────────────────────────────────────────────────

@dataclass(frozen=True)
class RelatedConfig:
    """Controls related document discovery and ranking."""
    min_similarity: float = 0.7          # below this → not shown at all
    auto_suggest_similarity: float = 0.7  # threshold for auto-adding to frontmatter
    auto_suggest_max: int = 3             # max auto-suggested related docs
    hnsw_candidates: int = 20             # ChromaDB HNSW query breadth

    # Composite ranking formula weights (for sorting)
    # final_score = w_similarity * similarity + w_confidence * (confidence / 100)
    w_similarity: float = 0.6
    w_confidence: float = 0.4

    # UI display
    default_visible: int = 2              # show N items by default, rest behind "더 보기"
    max_results: int = 10                 # hard cap


# ── RAG Boost ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RAGBoostConfig:
    """Controls how confidence affects RAG source ranking."""
    # adjusted_relevance = base * (floor + (1-floor) * confidence / 100)
    # floor=0.7 means: confidence 0 → 70% weight, confidence 100 → 100% weight
    floor: float = 0.7


# ── Conflict Detection ───────────────────────────────────────────────

@dataclass(frozen=True)
class ConflictConfig:
    """Controls conflict/duplicate detection thresholds."""
    similarity_threshold: float = field(
        default_factory=lambda: _env_float("ONTONG_CONFLICT_THRESHOLD", 0.85)
    )
    hnsw_n_results: int = 20
    max_results: int = 200


# ── Top-level config ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoringConfig:
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    related: RelatedConfig = field(default_factory=RelatedConfig)
    rag_boost: RAGBoostConfig = field(default_factory=RAGBoostConfig)
    conflict: ConflictConfig = field(default_factory=ConflictConfig)

    def explain(self) -> dict:
        """Return human-readable explanation of all scoring parameters.

        Intended for developer debugging and tuning dashboards.
        """
        return {
            "confidence": {
                "description": "문서 신뢰도 점수 (0-100). 높을수록 신뢰할 수 있는 문서.",
                "formula": "가중합: freshness*{fw} + status*{sw} + metadata*{mw} + backlinks*{bw} + owner*{ow} + feedback*{fbw}".format(
                    fw=self.confidence.weights.freshness,
                    sw=self.confidence.weights.status,
                    mw=self.confidence.weights.metadata,
                    bw=self.confidence.weights.backlinks,
                    ow=self.confidence.weights.owner_activity,
                    fbw=self.confidence.weights.user_feedback,
                ),
                "weights": {
                    "freshness": f"{self.confidence.weights.freshness}% — 최근 수정일 기준 선형 감쇠 (0개월=100, {self.confidence.thresholds.freshness_decay_months}개월=0)",
                    "status": f"{self.confidence.weights.status}% — deprecated=0, draft=40, approved=100",
                    "metadata": f"{self.confidence.weights.metadata}% — (domain + process + tags + created_by) / 4",
                    "backlinks": f"{self.confidence.weights.backlinks}% — min(역참조 수 / 3, 1.0)",
                    "owner_activity": f"{self.confidence.weights.owner_activity}% — 작성자 최근 90일 활동 여부",
                    "user_feedback": f"{self.confidence.weights.user_feedback}% — 확인/수정요청 비율 (피드백 없으면 50)",
                },
                "tiers": {
                    "high": f"{self.confidence.thresholds.high_min}+",
                    "medium": f"{self.confidence.thresholds.medium_min}-{self.confidence.thresholds.high_min - 1}",
                    "low": f"0-{self.confidence.thresholds.medium_min - 1}",
                },
                "stale_threshold": f"{self.confidence.thresholds.stale_months}개월",
            },
            "related_documents": {
                "description": "관련 문서 발견 및 랭킹. 임베딩 유사도 + 신뢰도 복합 점수로 정렬.",
                "composite_formula": f"{self.related.w_similarity} × 유사도 + {self.related.w_confidence} × (신뢰도 / 100)",
                "min_similarity": self.related.min_similarity,
                "auto_suggest": f"저장 시 유사도 {self.related.auto_suggest_similarity}+ 상위 {self.related.auto_suggest_max}건 자동 추가",
                "ui_default_visible": self.related.default_visible,
            },
            "rag_boost": {
                "description": "RAG 검색 결과에서 신뢰도에 따른 순위 보정.",
                "formula": f"adjusted = base_relevance × ({self.rag_boost.floor} + {round(1 - self.rag_boost.floor, 2)} × confidence / 100)",
                "effect": f"신뢰도 100 → 100% 반영, 신뢰도 0 → {int(self.rag_boost.floor * 100)}% 반영",
            },
            "conflict_detection": {
                "description": "임베딩 유사도 기반 유사 문서 감지.",
                "similarity_threshold": self.conflict.similarity_threshold,
            },
        }


# Singleton — import this everywhere
SCORING = ScoringConfig()
