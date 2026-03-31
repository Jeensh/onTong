"""Stress test: measure tree loading, search index, and reindex at various file counts."""

import asyncio
import time
import httpx
import json
import sys

BASE = "http://localhost:8001"
TIMEOUT = httpx.Timeout(300.0)


async def create_files(client: httpx.AsyncClient, count: int, start_from: int = 0):
    """Create test files in batches."""
    sem = asyncio.Semaphore(20)  # limit concurrency

    async def _create_one(i: int):
        async with sem:
            folder = f"stress-test/dept-{i // 100:03d}"
            path = f"{folder}/doc-{i:05d}.md"
            content = (
                f"---\ntitle: Test Document {i}\ndomain: dept-{i // 100:03d}\n"
                f"tags:\n  - stress-test\n  - batch-{i // 500}\n---\n\n"
                f"# Test Document {i}\n\n"
                f"This is a test document for stress testing. "
                f"It belongs to department {i // 100} and batch {i // 500}.\n\n"
                + ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 20)
                + f"\n\n## Section {i}\n\nAdditional content for document {i}.\n"
            )
            try:
                await client.put(f"{BASE}/api/wiki/file/{path}", json={"content": content})
            except Exception as e:
                print(f"  Error creating {path}: {e}")

    tasks = [_create_one(i) for i in range(start_from, start_from + count)]
    for batch_start in range(0, len(tasks), 100):
        batch = tasks[batch_start:batch_start + 100]
        await asyncio.gather(*batch)
        print(f"  Created {min(batch_start + 100, len(tasks))}/{len(tasks)} files")


async def measure_tree_load(client: httpx.AsyncClient):
    """Measure tree loading time and response size."""
    start = time.time()
    resp = await client.get(f"{BASE}/api/wiki/tree")
    elapsed = time.time() - start
    return elapsed, len(resp.content), resp.status_code


async def measure_tree_etag(client: httpx.AsyncClient):
    """Measure ETag 304 response time."""
    resp1 = await client.get(f"{BASE}/api/wiki/tree")
    etag = resp1.headers.get("etag")
    if not etag:
        return None, None, None

    start = time.time()
    resp2 = await client.get(f"{BASE}/api/wiki/tree", headers={"If-None-Match": etag})
    elapsed = time.time() - start
    return elapsed, resp2.status_code, etag


async def measure_search_index(client: httpx.AsyncClient):
    """Measure search index loading time."""
    start = time.time()
    resp = await client.get(f"{BASE}/api/search/index")
    elapsed = time.time() - start
    return elapsed, len(resp.content)


async def measure_reindex(client: httpx.AsyncClient):
    """Measure reindex time."""
    start = time.time()
    resp = await client.post(f"{BASE}/api/wiki/reindex")
    elapsed = time.time() - start
    data = resp.json() if resp.status_code == 200 else {}
    return elapsed, data.get("total_chunks", 0)


async def count_tree_nodes(client: httpx.AsyncClient) -> int:
    """Count total nodes in tree."""
    resp = await client.get(f"{BASE}/api/wiki/tree")
    tree = resp.json()

    def _count(nodes):
        total = len(nodes)
        for n in nodes:
            if n.get("children"):
                total += _count(n["children"])
        return total

    return _count(tree)


async def cleanup(client: httpx.AsyncClient):
    """Delete all stress test files."""
    print("\nCleaning up stress-test files...")
    try:
        resp = await client.get(f"{BASE}/api/wiki/tree")
        tree = resp.json()

        def _find_stress(nodes):
            for n in nodes:
                if n["name"] == "stress-test":
                    return n
                if n.get("children"):
                    found = _find_stress(n["children"])
                    if found:
                        return found
            return None

        stress_node = _find_stress(tree)
        if not stress_node:
            return

        # Collect all file paths
        def _collect_files(node, files):
            if not node.get("is_dir"):
                files.append(node["path"])
            for child in node.get("children", []):
                _collect_files(child, files)

        files = []
        _collect_files(stress_node, files)

        # Delete files
        sem = asyncio.Semaphore(20)
        async def _del(path):
            async with sem:
                await client.delete(f"{BASE}/api/wiki/file/{path}")

        for batch_start in range(0, len(files), 100):
            batch = [_del(f) for f in files[batch_start:batch_start + 100]]
            await asyncio.gather(*batch)
            print(f"  Deleted {min(batch_start + 100, len(files))}/{len(files)} files")

        # Delete folders (bottom up)
        def _collect_folders(node, folders, depth=0):
            if node.get("is_dir"):
                for child in node.get("children", []):
                    _collect_folders(child, folders, depth + 1)
                folders.append((depth, node["path"]))

        folders = []
        _collect_folders(stress_node, folders)
        folders.sort(key=lambda x: -x[0])  # deepest first

        for _, folder_path in folders:
            try:
                await client.delete(f"{BASE}/api/wiki/folder/{folder_path}")
            except Exception:
                pass

        print("  Cleanup done.")
    except Exception as e:
        print(f"  Cleanup error: {e}")


async def main():
    scales = [100, 500, 1000, 2000, 5000]
    results = []

    # Check for --no-cleanup flag
    do_cleanup = "--no-cleanup" not in sys.argv
    # Check for --scales flag
    for arg in sys.argv:
        if arg.startswith("--scales="):
            scales = [int(x) for x in arg.split("=")[1].split(",")]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Clean up any previous stress test data
        await cleanup(client)

        cumulative = 0
        for count in scales:
            to_create = count - cumulative
            print(f"\n{'='*60}")
            print(f"  Scale: {count} files (creating {to_create} new)")
            print(f"{'='*60}")

            # Create files
            if to_create > 0:
                t0 = time.time()
                await create_files(client, to_create, start_from=cumulative)
                create_time = time.time() - t0
                print(f"  File creation: {create_time:.1f}s")
            cumulative = count

            # Count tree nodes
            node_count = await count_tree_nodes(client)
            print(f"  Tree nodes: {node_count}")

            # Measure tree load
            tree_time, tree_size, tree_status = await measure_tree_load(client)
            print(f"  Tree load: {tree_time:.3f}s ({tree_size/1024:.0f} KB)")

            # Measure ETag
            etag_time, etag_status, _ = await measure_tree_etag(client)
            if etag_time is not None:
                print(f"  ETag 304:  {etag_time:.3f}s (status={etag_status})")

            # Measure search index
            idx_time, idx_size = await measure_search_index(client)
            print(f"  Search index: {idx_time:.3f}s ({idx_size/1024:.0f} KB)")

            # Measure reindex
            reindex_time, chunks = await measure_reindex(client)
            print(f"  Reindex: {reindex_time:.1f}s ({chunks} chunks)")

            result = {
                "files": count,
                "tree_nodes": node_count,
                "tree_time_s": round(tree_time, 3),
                "tree_size_kb": round(tree_size / 1024),
                "etag_time_s": round(etag_time, 3) if etag_time else None,
                "etag_status": etag_status,
                "index_time_s": round(idx_time, 3),
                "index_size_kb": round(idx_size / 1024),
                "reindex_time_s": round(reindex_time, 1),
                "reindex_chunks": chunks,
            }
            results.append(result)

        # Summary table
        print(f"\n{'='*60}")
        print("  SUMMARY")
        print(f"{'='*60}")
        print(f"{'Files':>7} | {'Tree':>8} | {'Tree KB':>8} | {'ETag':>8} | {'Index':>8} | {'Idx KB':>8} | {'Reindex':>8} | {'Chunks':>7}")
        print("-" * 80)
        for r in results:
            etag_str = f"{r['etag_time_s']:.3f}s" if r['etag_time_s'] else "N/A"
            print(
                f"{r['files']:>7} | {r['tree_time_s']:>7.3f}s | {r['tree_size_kb']:>6} KB | "
                f"{etag_str:>8} | {r['index_time_s']:>7.3f}s | {r['index_size_kb']:>6} KB | "
                f"{r['reindex_time_s']:>6.1f}s | {r['reindex_chunks']:>7}"
            )

        # Save results
        with open("tests/stress/results_tree_scale.json", "w") as f:
            json.dump(results, f, indent=2)
        print("\nResults saved to tests/stress/results_tree_scale.json")

        # Cleanup
        if do_cleanup:
            await cleanup(client)
        else:
            print("\nSkipping cleanup (--no-cleanup)")


if __name__ == "__main__":
    asyncio.run(main())
