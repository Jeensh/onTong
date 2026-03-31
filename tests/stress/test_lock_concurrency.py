"""Stress test: lock service concurrency and throughput."""

import asyncio
import time
import httpx
import json
import sys

BASE = "http://localhost:8001"
TIMEOUT = httpx.Timeout(60.0)


async def lock_unlock_cycle(client: httpx.AsyncClient, user_id: int, n_files: int, results: list, errors: list):
    """Single user: acquire and release locks on multiple files."""
    user = f"stress-user-{user_id:03d}"
    successes = 0
    conflicts = 0

    for i in range(n_files):
        path = f"lock-test/doc-{(user_id * n_files + i) % 500:03d}.md"
        try:
            # Acquire
            resp = await client.post(f"{BASE}/api/lock", json={"path": path, "user": user})
            data = resp.json()
            if data.get("locked"):
                successes += 1
            else:
                conflicts += 1

            # Release
            await client.request("DELETE", f"{BASE}/api/lock", params={"path": path, "user": user})
        except Exception as e:
            errors.append(f"User {user_id}: {str(e)[:80]}")

    results.append({"user": user_id, "successes": successes, "conflicts": conflicts})


async def contention_test(client: httpx.AsyncClient, n_users: int):
    """Multiple users try to lock the SAME file simultaneously."""
    path = "lock-test/shared-doc.md"
    results = []

    async def _try_lock(user_id):
        user = f"contention-user-{user_id}"
        resp = await client.post(f"{BASE}/api/lock", json={"path": path, "user": user})
        data = resp.json()
        results.append({
            "user": user_id,
            "got_lock": data.get("locked", False),
            "locked_by": data.get("locked_by"),
        })

    await asyncio.gather(*[_try_lock(i) for i in range(n_users)])

    winners = [r for r in results if r["got_lock"]]
    losers = [r for r in results if not r["got_lock"]]

    # Cleanup
    for r in winners:
        await client.request("DELETE", f"{BASE}/api/lock", params={"path": path, "user": f"contention-user-{r['user']}"})

    return len(winners), len(losers)


async def main():
    configs = [
        {"users": 10, "files_per_user": 20},
        {"users": 25, "files_per_user": 20},
        {"users": 50, "files_per_user": 20},
        {"users": 100, "files_per_user": 10},
    ]

    all_results = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Test 1: Throughput
        print("=" * 50)
        print("  Test 1: Lock/Unlock Throughput")
        print("=" * 50)

        for cfg in configs:
            n_users = cfg["users"]
            n_files = cfg["files_per_user"]
            total_ops = n_users * n_files * 2  # lock + unlock

            results = []
            errors = []

            start = time.time()
            tasks = [
                lock_unlock_cycle(client, i, n_files, results, errors)
                for i in range(n_users)
            ]
            await asyncio.gather(*tasks)
            elapsed = time.time() - start

            total_successes = sum(r["successes"] for r in results)
            total_conflicts = sum(r["conflicts"] for r in results)
            ops_per_sec = total_ops / elapsed if elapsed > 0 else 0

            summary = {
                "users": n_users,
                "files_per_user": n_files,
                "total_ops": total_ops,
                "elapsed_s": round(elapsed, 2),
                "ops_per_sec": round(ops_per_sec),
                "successes": total_successes,
                "conflicts": total_conflicts,
                "errors": len(errors),
            }
            all_results.append(summary)

            print(f"\n  {n_users} users × {n_files} files:")
            print(f"    {total_ops} ops in {elapsed:.2f}s = {ops_per_sec:.0f} ops/sec")
            print(f"    Successes: {total_successes} | Conflicts: {total_conflicts} | Errors: {len(errors)}")

            if errors:
                for e in errors[:3]:
                    print(f"    Error: {e}")

        # Test 2: Contention (same file)
        print(f"\n{'='*50}")
        print("  Test 2: Lock Contention (same file)")
        print(f"{'='*50}")

        contention_results = []
        for n in [10, 25, 50, 100]:
            winners, losers = await contention_test(client, n)
            contention_results.append({"users": n, "winners": winners, "losers": losers})
            print(f"  {n} users → {winners} got lock, {losers} blocked")
            if winners != 1:
                print(f"  ⚠️  Expected exactly 1 winner, got {winners}!")

        # Summary
        print(f"\n{'='*50}")
        print("  THROUGHPUT SUMMARY")
        print(f"{'='*50}")
        print(f"{'Users':>6} | {'Files':>6} | {'Ops':>6} | {'Time':>7} | {'Ops/s':>7} | {'OK':>5} | {'Conflict':>8} | {'Err':>4}")
        print("-" * 70)
        for r in all_results:
            print(
                f"{r['users']:>6} | {r['files_per_user']:>6} | {r['total_ops']:>6} | "
                f"{r['elapsed_s']:>6.2f}s | {r['ops_per_sec']:>7} | {r['successes']:>5} | "
                f"{r['conflicts']:>8} | {r['errors']:>4}"
            )

        print(f"\n  CONTENTION SUMMARY")
        for c in contention_results:
            status = "✅" if c["winners"] == 1 else "⚠️"
            print(f"  {status} {c['users']} users → {c['winners']} winner(s)")

        # Save
        output = {"throughput": all_results, "contention": contention_results}
        with open("tests/stress/results_lock.json", "w") as f:
            json.dump(output, f, indent=2)
        print("\nResults saved to tests/stress/results_lock.json")


if __name__ == "__main__":
    asyncio.run(main())
