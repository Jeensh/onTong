"""Surgical body patcher for path renames using RefIndex offsets."""
from __future__ import annotations

from dataclasses import dataclass
from backend.application.refindex.extractor import Reference


@dataclass(frozen=True)
class PatchResult:
    new_content: str
    applied: int           # number of refs successfully replaced
    skipped: int           # refs whose offset/raw didn't match (stale index)


def patch_references(
    raw_content: str,
    refs: list[Reference],
    target_remap: dict[str, str],
) -> PatchResult:
    """Replace each Reference's location-pointed substring with the new target.

    target_remap = {old_target_path: new_target_path}.
    For BODY_WIKILINK refs (kind=4), target is a stem; the remap key MUST be the stem
    (not the full path). The caller is responsible for stem→stem mapping.

    Algorithm:
    1. Filter to only those refs whose target is in the remap.
    2. Sort refs by location.offset DESCENDING (so later edits don't shift earlier offsets).
    3. For each ref: verify raw_content[offset:offset+length] == ref.location["raw"]
       (sanity check against stale index). If mismatch, skip + count.
    4. Replace with target_remap[ref.target_path] if it's in the map.
    5. Build the new content via slice + concat.
    """
    if not refs or not target_remap:
        return PatchResult(new_content=raw_content, applied=0, skipped=0)

    # Filter to only those refs whose target is in the remap
    relevant = [r for r in refs if r.target_path in target_remap]
    # Sort by offset descending so right-to-left edits don't invalidate earlier offsets
    relevant.sort(key=lambda r: -r.location["offset"])

    chars = raw_content
    applied = 0
    skipped = 0

    for r in relevant:
        off = r.location["offset"]
        length = r.location["length"]
        expected_raw = r.location["raw"]
        if chars[off:off + length] != expected_raw:
            skipped += 1
            continue
        new_target = target_remap[r.target_path]
        chars = chars[:off] + new_target + chars[off + length:]
        applied += 1

    return PatchResult(new_content=chars, applied=applied, skipped=skipped)
