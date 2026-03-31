"""Stress test: simulate concurrent users performing typical operations."""

import asyncio
import time
import httpx
import json
import sys

BASE = "http://localhost:8001"
TIMEOUT = httpx.Timeout(60.0)


async def setup_test_files(client: httpx.AsyncClient, count: int = 50):
    """Create test files for concurrent access."""
    sem = asyncio.Semaphore(20)

    async def _create(i):
        async with sem:
            path = f"concurrent-test/doc-{i:03d}.md"
            content = (
                f"---\ntitle: Concurrent Test Doc {i}\n---\n\n"
                f"# Document {i}\n\nTest content for concurrent access testing.\n"
                + ("Additional paragraph. " * 30)
            )
            await client.put(f"{BASE}/api/wiki/file/{path}", json={"content": content})

    await asyncio.gather(*[_create(i) for i in range(count)])
    print(f"  Setup: created {count} test files")


async def simulate_user(user_id: int, results: list, errors: list):
    """Simulate a single user: tree → file read → search → file read."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        timings = {}
        start = time.time()

        try:
            # 1) Tree loading
            t0 = time.time()
            resp = await client.get(f"{BASE}/api/wiki/tree")
            timings["tree"] = time.time() - t0
            if resp.status_code != 200:
                errors.append(f"User {user_id}: tree failed ({resp.status_code})")

            # 2) File read
            t0 = time.time()
            file_idx = user_id % 50
            resp = await client.get(f"{BASE}/api/wiki/file/concurrent-test/doc-{file_idx:03d}.md")
            timings["file_read"] = time.time() - t0

            # 3) Search (hybrid)
            t0 = time.time()
            resp = await client.get(f"{BASE}/api/search/hybrid", params={"q": f"document {user_id}", "n": 10})
            timings["search"] = time.time() - t0

            # 4) Another file read
            t0 = time.time()
            file_idx2 = (user_id + 25) % 50
            resp = await client.get(f"{BASE}/api/wiki/file/concurrent-test/doc-{file_idx2:03d}.md")
            timings["file_read_2"] = time.time() - t0

            total = time.time() - start
            results.append({
                "user": user_id,
                "total": round(total, 3),
                **{k: round(v, 3) for k, v in timings.items()},
            })
        except Exception as e:
            errors.append(f"User {user_id}: {str(e)[:100]}")


async def cleanup(client: httpx.AsyncClient):
    """Remove test files."""
    print("\nCleaning up...")
    try:
        for i in range(50):
            await client.delete(f"{BASE}/api/wiki/file/concurrent-test/doc-{i:03d}.md")
        await client.delete(f"{BASE}/api/wiki/folder/concurrent-test")
        print("  Cleanup done.")
    except Exception:
        pass


async def main():
    concurrency_levels = [10, 25, 50, 100]

    for arg in sys.argv:
        if arg.startswith("--levels="):
            concurrency_levels = [int(x) for x in arg.split("=")[1].split(",")]

    all_summaries = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Setup
        await cleanup(client)
        await setup_test_files(client)

        # Warm up
        await client.get(f"{BASE}/api/wiki/tree")

        for n_users in concurrency_levels:
            print(f"\n{'='*50}")
            print(f"  {n_users} concurrent users")
            print(f"{'='*50}")

            results = []
            errors = []

            wall_start = time.time()
            tasks = [simulate_user(i, results, errors) for i in range(n_users)]
            await asyncio.gather(*tasks)
            wall_time = time.time() - wall_start

            if errors:
                print(f"  Errors: {len(errors)}")
                for e in errors[:5]:
                    print(f"    {e}")

            if results:
                totals = sorted([r["total"] for r in results])
                trees = sorted([r.get("tree", 0) for r in results])
                searches = sorted([r.get("search", 0) for r in results])

                avg = sum(totals) / len(totals)
                p50 = totals[len(totals) // 2]
                p95 = totals[int(len(totals) * 0.95)]
                p99 = totals[int(len(totals) * 0.99)]
                max_t = totals[-1]

                tree_p95 = trees[int(len(trees) * 0.95)]
                search_p95 = searches[int(len(searches) * 0.95)]

                summary = {
                    "users": n_users,
                    "wall_time": round(wall_time, 2),
                    "avg": round(avg, 3),
                    "p50": round(p50, 3),
                    "p95": round(p95, 3),
                    "p99": round(p99, 3),
                    "max": round(max_t, 3),
                    "tree_p95": round(tree_p95, 3),
                    "search_p95": round(search_p95, 3),
                    "errors": len(errors),
                }
                all_summaries.append(summary)

                print(f"  Wall time: {wall_time:.2f}s")
                print(f"  Avg: {avg:.3f}s | P50: {p50:.3f}s | P95: {p95:.3f}s | P99: {p99:.3f}s | Max: {max_t:.3f}s")
                print(f"  Tree P95: {tree_p95:.3f}s | Search P95: {search_p95:.3f}s")

                if p95 > 3.0:
                    print(f"  ⚠️  P95 > 3s — user experience degraded")
                elif p95 > 1.0:
                    print(f"  ⚠️  P95 > 1s — noticeable delay")
                else:
                    print(f"  ✅ P95 < 1s — acceptable")

        # Summary table
        print(f"\n{'='*50}")
        print("  SUMMARY")
        print(f"{'='*50}")
        print(f"{'Users':>6} | {'Wall':>6} | {'Avg':>7} | {'P50':>7} | {'P95':>7} | {'P99':>7} | {'Max':>7} | {'Err':>4}")
        print("-" * 70)
        for s in all_summaries:
            print(
                f"{s['users']:>6} | {s['wall_time']:>5.2f}s | {s['avg']:>6.3f}s | "
                f"{s['p50']:>6.3f}s | {s['p95']:>6.3f}s | {s['p99']:>6.3f}s | "
                f"{s['max']:>6.3f}s | {s['errors']:>4}"
            )

        # Save
        with open("tests/stress/results_concurrent.json", "w") as f:
            json.dump(all_summaries, f, indent=2)
        print("\nResults saved to tests/stress/results_concurrent.json")

        # Cleanup
        await cleanup(client)


if __name__ == "__main__":
    asyncio.run(main())
