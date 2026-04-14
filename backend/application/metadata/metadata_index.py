"""Materialized metadata index — O(1) reads, incremental writes.

Maintains `.ontong/metadata_index.json` with aggregated counts:
  - domains: {domain: count}
  - domain_processes: {domain: {process: count}}
  - tags: {tag: count}
  - untagged: [path, ...]
  - files: {path: {domain, process, tags[], status, supersedes, superseded_by, ...}}

Reverse indexes for O(1) file lookups:
  - domain_files: {domain: [path, ...]}
  - process_files: {process: [path, ...]}
  - tag_files: {tag: [path, ...]}
  - supersedes_index: {target_path: [paths_that_supersede_it]}
  - related_index: {target_path: [paths_that_reference_it_in_related]}
  - status_files: {status: [path, ...]}

Rebuilt fully on reindex; updated incrementally on file save/delete.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MetadataIndex:
    """Thread-safe materialized metadata index."""

    def __init__(self, wiki_dir: str) -> None:
        self._path = Path(wiki_dir) / ".ontong" / "metadata_index.json"
        self._lock = threading.Lock()
        self._data: dict[str, Any] | None = None

    # ── Public read API ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return {domains: {d: count}, tags: {t: count}, untagged_count: int}."""
        d = self._load()
        return {
            "domains": d.get("domains", {}),
            "domain_processes": d.get("domain_processes", {}),
            "tags": d.get("tags", {}),
            "untagged_count": len(d.get("untagged", [])),
        }

    def get_untagged(self, offset: int = 0, limit: int = 50) -> dict:
        """Return paginated untagged file list."""
        d = self._load()
        all_untagged: list[str] = d.get("untagged", [])
        page = all_untagged[offset : offset + limit]
        return {
            "files": [{"path": p, "title": p.rsplit("/", 1)[-1]} for p in page],
            "count": len(all_untagged),
            "offset": offset,
            "limit": limit,
        }

    def search_tags(self, query: str, limit: int = 15) -> list[str]:
        """Prefix search on tag names."""
        d = self._load()
        tags: dict[str, int] = d.get("tags", {})
        q = query.lower()
        matches = [t for t in tags if q in t.lower()]
        # Sort by count desc, then alphabetically
        matches.sort(key=lambda t: (-tags[t], t))
        return matches[:limit]

    def get_all_tag_names(self) -> list[str]:
        """Return all unique tag names sorted."""
        d = self._load()
        return sorted(d.get("tags", {}).keys())

    def get_all_domains(self) -> list[str]:
        """Return all domains that have at least one document."""
        d = self._load()
        return sorted(d.get("domains", {}).keys())

    def get_all_processes(self) -> list[str]:
        """Return all processes that have at least one document."""
        d = self._load()
        result: set[str] = set()
        for procs in d.get("domain_processes", {}).values():
            result.update(procs.keys())
        return sorted(result)

    def get_files_by_field(self, field: str, value: str, offset: int = 0, limit: int = 50) -> dict:
        """Return paginated file paths matching a metadata field value. O(1) via reverse index."""
        d = self._load()
        if field == "domain":
            all_files = d.get("domain_files", {}).get(value, [])
        elif field == "process":
            all_files = d.get("process_files", {}).get(value, [])
        elif field == "tags":
            all_files = d.get("tag_files", {}).get(value, [])
        else:
            all_files = []
        page = all_files[offset : offset + limit]
        return {"files": page, "total": len(all_files), "offset": offset, "limit": limit}

    def get_neighbor_tags(self, parent_dir: str, exclude_path: str = "", top_k: int = 20) -> list[tuple[str, int]]:
        """Aggregate tag usage among files sharing the same parent directory.

        Returns [(tag, count), ...] sorted by count desc.
        Used by auto-tag suggestion to provide directory-local vocabulary as a strong signal.
        Excludes deprecated files.
        """
        d = self._load()
        files: dict = d.get("files", {})
        prefix = parent_dir.rstrip("/") + "/" if parent_dir else ""
        tag_counts: dict[str, int] = {}
        for path, entry in files.items():
            if path == exclude_path:
                continue
            if entry.get("status") == "deprecated":
                continue
            if prefix and not path.startswith(prefix):
                continue
            # Only direct children, not deeper descendants
            relative = path[len(prefix):] if prefix else path
            if "/" in relative:
                continue
            for t in entry.get("tags", []) or []:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        items = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
        return items[:top_k]

    def get_neighbor_domain_summary(self, parent_dir: str, exclude_path: str = "") -> dict:
        """Return {domain: count, processes: {process: count}} for files in the same directory.

        Used by Pass 1 (domain/process inference) as a strong locality signal.
        Excludes deprecated files.
        """
        d = self._load()
        files: dict = d.get("files", {})
        prefix = parent_dir.rstrip("/") + "/" if parent_dir else ""
        domains: dict[str, int] = {}
        processes: dict[str, int] = {}
        for path, entry in files.items():
            if path == exclude_path:
                continue
            if entry.get("status") == "deprecated":
                continue
            if prefix and not path.startswith(prefix):
                continue
            relative = path[len(prefix):] if prefix else path
            if "/" in relative:
                continue
            dom = entry.get("domain", "")
            proc = entry.get("process", "")
            if dom:
                domains[dom] = domains.get(dom, 0) + 1
            if proc:
                processes[proc] = processes.get(proc, 0) + 1
        return {"domains": domains, "processes": processes}

    def get_tags_for_domain(self, domain: str, top_k: int = 50) -> list[tuple[str, int]]:
        """Aggregate tag usage among files in a given domain.

        Returns [(tag, count), ...] sorted by count desc.
        Used by Pass 2 to inject domain-frequent vocabulary into the tags prompt.
        """
        d = self._load()
        files: dict = d.get("files", {})
        domain_files: list[str] = d.get("domain_files", {}).get(domain, [])
        tag_counts: dict[str, int] = {}
        for path in domain_files:
            entry = files.get(path) or {}
            for t in entry.get("tags", []) or []:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        items = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
        return items[:top_k]

    def get_tags_for_paths(self, paths: list[str]) -> list[str]:
        """Return the union of tags from a set of file paths (used for related_docs signal)."""
        d = self._load()
        files: dict = d.get("files", {})
        result: set[str] = set()
        for p in paths:
            entry = files.get(p) or {}
            for t in entry.get("tags", []) or []:
                result.add(t)
        return sorted(result)

    def search_tags_paginated(self, query: str, offset: int = 0, limit: int = 30) -> dict:
        """Paginated tag search with counts."""
        d = self._load()
        tags: dict[str, int] = d.get("tags", {})
        if query:
            q = query.lower()
            matches = [(t, c) for t, c in tags.items() if q in t.lower()]
        else:
            matches = list(tags.items())
        matches.sort(key=lambda x: (-x[1], x[0]))
        total = len(matches)
        page = matches[offset : offset + limit]
        return {"tags": [{"name": t, "count": c} for t, c in page], "total": total}

    # ── Lineage / status query API ─────────────────────────────────

    def get_file_entry(self, path: str) -> dict | None:
        """Return the full index entry for a file, or None if not found."""
        d = self._load()
        return d.get("files", {}).get(path)

    def get_supersedes_reverse(self, path: str) -> list[str]:
        """Return paths that claim to supersede the given path."""
        d = self._load()
        return list(d.get("supersedes_index", {}).get(path, []))

    def get_related_reverse(self, path: str) -> list[str]:
        """Return paths that reference the given path in their 'related' field."""
        d = self._load()
        return list(d.get("related_index", {}).get(path, []))

    def get_files_by_status(self, status: str) -> list[str]:
        """Return all file paths with the given status."""
        d = self._load()
        return list(d.get("status_files", {}).get(status, []))

    def get_all_statuses(self) -> dict[str, str]:
        """Return {path: status} map for all files that have a non-empty status."""
        d = self._load()
        result: dict[str, str] = {}
        for path, entry in d.get("files", {}).items():
            s = entry.get("status", "")
            if s:
                result[path] = s
        return result

    # ── Write API (called by wiki_service) ───────────────────────────

    def on_file_saved(
        self,
        path: str,
        domain: str,
        process: str,
        tags: list[str],
        *,
        updated: str = "",
        updated_by: str = "",
        created_by: str = "",
        related: list[str] | None = None,
        status: str = "",
        supersedes: str = "",
        superseded_by: str = "",
    ) -> None:
        """Incremental update after a file is saved."""
        with self._lock:
            d = self._load()
            files: dict = d.setdefault("files", {})

            # Remove old counts for this file
            old = files.get(path)
            if old:
                self._decrement(d, old, path)

            # Preserve created_by from previous entry if not provided
            if not created_by and old:
                created_by = old.get("created_by", "")

            # Add new counts
            new_entry = {
                "domain": domain,
                "process": process,
                "tags": tags,
                "updated": updated,
                "updated_by": updated_by,
                "created_by": created_by,
                "related": related or [],
                "status": status,
                "supersedes": supersedes,
                "superseded_by": superseded_by,
            }
            files[path] = new_entry
            self._increment(d, new_entry, path)

            # Update untagged list
            untagged: list[str] = d.setdefault("untagged", [])
            is_untagged = not domain and not process and not tags
            if is_untagged and path not in untagged:
                untagged.append(path)
            elif not is_untagged and path in untagged:
                untagged.remove(path)

            self._save(d)

    def on_file_deleted(self, path: str) -> None:
        """Remove a file from the index."""
        with self._lock:
            d = self._load()
            files: dict = d.get("files", {})
            old = files.pop(path, None)
            if old:
                self._decrement(d, old, path)
            untagged: list[str] = d.get("untagged", [])
            if path in untagged:
                untagged.remove(path)
            self._save(d)

    def rebuild(self, file_metadata: list[tuple[str, str, str, list[str]]] | list[dict] = None, *, extended: list[dict] | None = None) -> None:
        """Full rebuild from file metadata.

        Accepts either:
        - Legacy format: list of (path, domain, process, tags) tuples
        - Extended format via `extended` kwarg: list of dicts with all fields
        """
        with self._lock:
            d: dict[str, Any] = {
                "domains": {},
                "domain_processes": {},
                "tags": {},
                "untagged": [],
                "files": {},
                "domain_files": {},
                "process_files": {},
                "tag_files": {},
                "status_files": {},
                "supersedes_index": {},
                "related_index": {},
            }

            items: list[dict] = []
            if extended is not None:
                items = extended
            elif file_metadata is not None:
                for item in file_metadata:
                    if isinstance(item, dict):
                        items.append(item)
                    else:
                        path, domain, process, tags = item
                        items.append({"path": path, "domain": domain, "process": process, "tags": tags})

            for item in items:
                path = item["path"]
                domain = item.get("domain", "")
                process = item.get("process", "")
                tags = item.get("tags", [])
                entry = {
                    "domain": domain,
                    "process": process,
                    "tags": tags,
                    "updated": item.get("updated", ""),
                    "updated_by": item.get("updated_by", ""),
                    "created_by": item.get("created_by", ""),
                    "related": item.get("related", []),
                    "status": item.get("status", ""),
                    "supersedes": item.get("supersedes", ""),
                    "superseded_by": item.get("superseded_by", ""),
                }
                d["files"][path] = entry
                self._increment(d, entry, path)
                if not domain and not process and not tags:
                    d["untagged"].append(path)

            self._save(d)
            logger.info(f"Metadata index rebuilt: {len(d['files'])} files")

    # ── Internal ─────────────────────────────────────────────────────

    def _increment(self, d: dict, entry: dict, path: str = "") -> None:
        domain = entry.get("domain", "")
        process = entry.get("process", "")
        tags = entry.get("tags", [])

        if domain:
            d.setdefault("domains", {})[domain] = d.get("domains", {}).get(domain, 0) + 1
            if path:
                df = d.setdefault("domain_files", {}).setdefault(domain, [])
                if path not in df:
                    df.append(path)
            if process:
                dp = d.setdefault("domain_processes", {}).setdefault(domain, {})
                dp[process] = dp.get(process, 0) + 1
                if path:
                    pf = d.setdefault("process_files", {}).setdefault(process, [])
                    if path not in pf:
                        pf.append(path)
        for t in tags:
            d.setdefault("tags", {})[t] = d.get("tags", {}).get(t, 0) + 1
            if path:
                tf = d.setdefault("tag_files", {}).setdefault(t, [])
                if path not in tf:
                    tf.append(path)

        # Reverse indexes for lineage
        if path:
            status = entry.get("status", "")
            if status:
                sf = d.setdefault("status_files", {}).setdefault(status, [])
                if path not in sf:
                    sf.append(path)

            supersedes = entry.get("supersedes", "")
            if supersedes:
                si = d.setdefault("supersedes_index", {}).setdefault(supersedes, [])
                if path not in si:
                    si.append(path)

            for rel in entry.get("related", []):
                ri = d.setdefault("related_index", {}).setdefault(rel, [])
                if path not in ri:
                    ri.append(path)

    def _decrement(self, d: dict, entry: dict, path: str = "") -> None:
        domain = entry.get("domain", "")
        process = entry.get("process", "")
        tags = entry.get("tags", [])

        if domain:
            domains = d.get("domains", {})
            if domain in domains:
                domains[domain] -= 1
                if domains[domain] <= 0:
                    del domains[domain]
            if path:
                df = d.get("domain_files", {}).get(domain, [])
                if path in df:
                    df.remove(path)
                if domain in d.get("domain_files", {}) and not d["domain_files"][domain]:
                    del d["domain_files"][domain]
            if process:
                dp = d.get("domain_processes", {}).get(domain, {})
                if process in dp:
                    dp[process] -= 1
                    if dp[process] <= 0:
                        del dp[process]
                if domain in d.get("domain_processes", {}) and not d["domain_processes"][domain]:
                    del d["domain_processes"][domain]
                if path:
                    pf = d.get("process_files", {}).get(process, [])
                    if path in pf:
                        pf.remove(path)
                    if process in d.get("process_files", {}) and not d["process_files"][process]:
                        del d["process_files"][process]
        for t in tags:
            tag_counts = d.get("tags", {})
            if t in tag_counts:
                tag_counts[t] -= 1
                if tag_counts[t] <= 0:
                    del tag_counts[t]
            if path:
                tf = d.get("tag_files", {}).get(t, [])
                if path in tf:
                    tf.remove(path)
                if t in d.get("tag_files", {}) and not d["tag_files"][t]:
                    del d["tag_files"][t]

        # Reverse indexes for lineage
        if path:
            status = entry.get("status", "")
            if status:
                sf = d.get("status_files", {}).get(status, [])
                if path in sf:
                    sf.remove(path)
                if status in d.get("status_files", {}) and not d["status_files"][status]:
                    del d["status_files"][status]

            supersedes = entry.get("supersedes", "")
            if supersedes:
                si = d.get("supersedes_index", {}).get(supersedes, [])
                if path in si:
                    si.remove(path)
                if supersedes in d.get("supersedes_index", {}) and not d["supersedes_index"][supersedes]:
                    del d["supersedes_index"][supersedes]

            for rel in entry.get("related", []):
                ri = d.get("related_index", {}).get(rel, [])
                if path in ri:
                    ri.remove(path)
                if rel in d.get("related_index", {}) and not d["related_index"][rel]:
                    del d["related_index"][rel]

    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                return self._data
            except Exception:
                pass
        self._data = {"domains": {}, "domain_processes": {}, "tags": {}, "untagged": [], "files": {}, "domain_files": {}, "process_files": {}, "tag_files": {}, "status_files": {}, "supersedes_index": {}, "related_index": {}}
        return self._data

    def _save(self, d: dict) -> None:
        self._data = d
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save metadata index: {e}")
