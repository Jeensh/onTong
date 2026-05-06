"""Seed N wiki docs for load testing.

Usage:
    python tests/load/seed_1k.py --count 1000 --base-url http://localhost:8002 --user-id donghae

Generates docs in 'load_test_demo/' with realistic cross-references.
"""
from __future__ import annotations

import argparse
import json
import random
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass
class SeedConfig:
    count: int
    base_url: str
    user_id: str
    folder: str = "load_test_demo"


def _put(cfg: SeedConfig, path: str, content: str) -> int:
    url = f"{cfg.base_url}/api/wiki/file/{urllib.parse.quote(path, safe='')}"
    req = urllib.request.Request(
        url,
        data=json.dumps({"content": content}).encode(),
        headers={"X-User-Id": cfg.user_id, "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except Exception:
        return -1


def make_doc(cfg: SeedConfig, idx: int, total: int) -> tuple[str, str]:
    path = f"{cfg.folder}/doc_{idx:05d}.md"
    # Pick 0-3 related docs (random)
    n_refs = random.randint(0, 3)
    related_refs = random.sample(range(total), min(n_refs, total - 1))
    related_refs = [r for r in related_refs if r != idx][:3]
    related_paths = [f"{cfg.folder}/doc_{r:05d}.md" for r in related_refs]

    fm_lines = ["---", "domain: load_test", "tags:", "  - load", "  - synthetic"]
    if related_paths:
        fm_lines.append("related:")
        for p in related_paths:
            fm_lines.append(f"  - {p}")
    fm_lines.append("---")

    body_lines = [
        f"# Doc {idx}",
        "",
        f"Synthetic load-test document #{idx} of {total}.",
        "",
    ]
    # Body refs (0-2 random sibling references via markdown link)
    for r in related_refs[:2]:
        body_lines.append(f"See [doc {r}]({cfg.folder}/doc_{r:05d}.md).")
    # Wikilink reference (1 random sibling)
    if total > 1:
        wl = random.randrange(total)
        if wl != idx:
            body_lines.append(f"Also [[doc_{wl:05d}]] for cross-ref testing.")

    content = "\n".join(fm_lines + [""] + body_lines + [""])
    return path, content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--base-url", default="http://localhost:8002")
    ap.add_argument("--user-id", default="donghae")
    ap.add_argument("--folder", default="load_test_demo")
    args = ap.parse_args()

    cfg = SeedConfig(count=args.count, base_url=args.base_url, user_id=args.user_id, folder=args.folder)
    print(f"Seeding {cfg.count} docs into {cfg.folder}/ via {cfg.base_url} ...")

    import time
    start = time.time()
    success = 0
    for i in range(cfg.count):
        path, content = make_doc(cfg, i, cfg.count)
        status = _put(cfg, path, content)
        if status == 200:
            success += 1
        if (i + 1) % 100 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f"  ... {i+1}/{cfg.count} done ({rate:.0f}/s)")

    elapsed = time.time() - start
    print(f"\nSeeded {success}/{cfg.count} in {elapsed:.1f}s ({success/elapsed:.0f}/s)")


if __name__ == "__main__":
    main()
