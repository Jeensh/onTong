"""CLI tool to batch-process existing wiki images.

Usage:
    python -m backend.cli.backfill_images                    # Process all
    python -m backend.cli.backfill_images --ocr-only         # OCR only (fast)
    python -m backend.cli.backfill_images --vision-only      # Vision only (images with OCR but no description)
    python -m backend.cli.backfill_images --dry-run           # Show what would be processed
    python -m backend.cli.backfill_images --reprocess         # Ignore cache, reprocess all
    python -m backend.cli.backfill_images --workers 8         # Parallel workers
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.config import settings
from backend.application.image.models import needs_processing

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def find_all_images(wiki_dir: Path) -> list[Path]:
    """Find all image files in wiki/assets/."""
    assets_dir = wiki_dir / "assets"
    if not assets_dir.exists():
        return []
    return sorted(
        f for f in assets_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in IMAGE_EXTENSIONS
        and not f.name.endswith(".meta.json")
    )


async def backfill(args: argparse.Namespace) -> None:
    """Run backfill processing."""
    wiki_dir = Path(settings.wiki_dir)
    all_images = find_all_images(wiki_dir)

    if not all_images:
        print("No images found in wiki/assets/")
        return

    if args.vision_only:
        from backend.application.image.models import load_sidecar
        vision_candidates = []
        for img in all_images:
            sidecar = load_sidecar(img)
            if sidecar and sidecar.ocr_text and not sidecar.description:
                vision_candidates.append(img)
        to_process = vision_candidates
        print(f"Found {len(all_images)} images total, {len(to_process)} need vision processing")
    elif args.reprocess:
        to_process = all_images
        print(f"Found {len(all_images)} images total, {len(to_process)} need processing (reprocess=True)")
    else:
        to_process = [img for img in all_images if needs_processing(img)]
        print(f"Found {len(all_images)} images total, {len(to_process)} need processing")

    if args.dry_run:
        for img in to_process:
            print(f"  Would process: {img.name}")
        return

    if not to_process:
        print("Nothing to process.")
        return

    from backend.application.image.ocr_engine import OCREngine
    from backend.application.image.vision_provider import create_vision_provider, NoopVisionProvider
    from backend.application.image.analyzer import ImageAnalyzer
    from backend.application.image.queue import ImageProcessingQueue

    ocr = OCREngine(
        languages=settings.image_ocr_languages.split(","),
        gpu=settings.image_ocr_gpu,
        confidence_threshold=settings.image_ocr_confidence,
    )

    if args.ocr_only:
        vision = NoopVisionProvider()
    else:
        vision = create_vision_provider(
            provider=settings.image_vision_provider,
            model=settings.image_vision_model,
            ollama_url=settings.ollama_host,
        )

    analyzer = ImageAnalyzer(ocr=ocr, vision=vision)
    queue = ImageProcessingQueue(analyzer)

    print(f"Processing {len(to_process)} images (vision: {vision.provider_name})...")

    result = await queue.process_images(to_process, force=args.reprocess, max_concurrent=args.workers)

    print(
        f"Done: {result['processed']} processed, "
        f"{result['skipped']} skipped, {result['errors']} errors"
    )


def main():
    parser = argparse.ArgumentParser(description="Backfill image analysis for wiki images")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--ocr-only", action="store_true", help="Only run OCR (skip vision)")
    parser.add_argument("--vision-only", action="store_true", help="Only run vision on images with existing OCR (skip OCR)")
    parser.add_argument("--reprocess", action="store_true", help="Reprocess all images")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    args = parser.parse_args()

    if args.ocr_only and args.vision_only:
        parser.error("--ocr-only and --vision-only are mutually exclusive")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(backfill(args))


if __name__ == "__main__":
    main()
