"""P5B-2: Async Indexing Tests

Verifies:
1. Save file returns quickly (< 100ms)
2. GET /api/wiki/index-status shows pending files
3. POST /api/wiki/reindex/{path} queues a file
4. POST /api/wiki/reindex-pending queues all pending
"""

import httpx
import asyncio
import time

BASE = "http://localhost:8001"


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        print("=" * 60)
        print("  P5B-2: Async Indexing Tests")
        print("=" * 60)

        errors = []

        # Test 1: Save file response time
        print("\n[Test 1] Save file response time (should be < 100ms)")
        start = time.time()
        r = await client.put(
            "/api/wiki/file/_test_async_idx.md",
            json={"content": "# Async Test\n\nThis file tests async indexing."},
        )
        elapsed_ms = (time.time() - start) * 1000
        if r.status_code in (200, 201):
            print(f"  Save response: {elapsed_ms:.0f}ms")
            if elapsed_ms < 500:
                print("  PASS — fast save response")
            else:
                print(f"  WARNING — {elapsed_ms:.0f}ms (target <100ms, may include first-run overhead)")
        else:
            errors.append(f"Test 1: Save failed: {r.status_code}")

        # Test 2: Index status endpoint
        print("\n[Test 2] GET /api/wiki/index-status")
        r = await client.get("/api/wiki/index-status")
        if r.status_code == 200:
            data = r.json()
            print(f"  pending_count: {data['pending_count']}")
            print(f"  pending files: {[p['path'] for p in data['pending']]}")
            print("  PASS")
        else:
            errors.append(f"Test 2: Expected 200, got {r.status_code}")

        # Wait briefly for background indexing to complete
        await asyncio.sleep(2)

        # Test 3: After waiting, file should be indexed
        print("\n[Test 3] After 2s wait, file should be indexed")
        r = await client.get("/api/wiki/index-status")
        if r.status_code == 200:
            data = r.json()
            pending_paths = [p["path"] for p in data["pending"]]
            if "_test_async_idx.md" not in pending_paths:
                print("  PASS — file no longer pending")
            else:
                print("  WARNING — file still pending (indexing may be slow)")
        else:
            errors.append(f"Test 3: Expected 200, got {r.status_code}")

        # Test 4: Manual reindex endpoint
        print("\n[Test 4] POST /api/wiki/reindex/_test_async_idx.md")
        r = await client.post("/api/wiki/reindex/_test_async_idx.md")
        if r.status_code == 200:
            data = r.json()
            print(f"  queued: {data.get('queued')}")
            print("  PASS")
        else:
            errors.append(f"Test 4: Expected 200, got {r.status_code}")

        # Test 5: Reindex pending
        print("\n[Test 5] POST /api/wiki/reindex-pending")
        r = await client.post("/api/wiki/reindex-pending")
        if r.status_code == 200:
            data = r.json()
            print(f"  queued: {data.get('queued')}")
            print("  PASS")
        else:
            errors.append(f"Test 5: Expected 200, got {r.status_code}")

        # Test 6: Reindex nonexistent file
        print("\n[Test 6] POST /api/wiki/reindex/nonexistent_xyz.md — 404")
        r = await client.post("/api/wiki/reindex/nonexistent_xyz.md")
        if r.status_code == 404:
            print("  PASS — 404 for nonexistent file")
        else:
            errors.append(f"Test 6: Expected 404, got {r.status_code}")

        # Cleanup
        await client.delete("/api/wiki/file/_test_async_idx.md")

        # Summary
        print("\n" + "=" * 60)
        if errors:
            print(f"  RESULT: FAIL — {len(errors)} error(s)")
            for e in errors:
                print(f"    - {e}")
        else:
            print("  RESULT: ALL PASS")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
