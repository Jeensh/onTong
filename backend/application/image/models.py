"""Image analysis data models and sidecar file I/O."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SIDECAR_VERSION = 1


@dataclass
class ImageAnalysis:
    ocr_text: str
    description: str
    provider: str
    ocr_engine: str
    processed_at: datetime

    def to_dict(self) -> dict:
        return {
            "version": SIDECAR_VERSION,
            "ocr_text": self.ocr_text,
            "description": self.description,
            "provider": self.provider,
            "ocr_engine": self.ocr_engine,
            "processed_at": self.processed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> ImageAnalysis:
        return cls(
            ocr_text=d.get("ocr_text", ""),
            description=d.get("description", ""),
            provider=d.get("provider", ""),
            ocr_engine=d.get("ocr_engine", ""),
            processed_at=datetime.fromisoformat(d["processed_at"]),
        )


def _meta_path_for(image_path: Path) -> Path:
    """Return the sidecar .meta.json path for an image."""
    return image_path.parent / (image_path.name + ".meta.json")


def save_sidecar(image_path: Path, analysis: ImageAnalysis) -> None:
    """Write analysis results to sidecar JSON file."""
    meta_path = _meta_path_for(image_path)
    meta_path.write_text(
        json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.debug(f"Saved sidecar: {meta_path}")


def load_sidecar(image_path: Path) -> ImageAnalysis | None:
    """Load analysis from sidecar JSON file. Returns None if not found."""
    meta_path = _meta_path_for(image_path)
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return ImageAnalysis.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to load sidecar {meta_path}: {e}")
        return None


def needs_processing(image_path: Path) -> bool:
    """Check if an image needs (re-)processing.

    Returns True if no sidecar exists or image is newer than sidecar.
    """
    meta_path = _meta_path_for(image_path)
    if not meta_path.exists():
        return True
    return image_path.stat().st_mtime > meta_path.stat().st_mtime
