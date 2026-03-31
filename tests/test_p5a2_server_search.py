"""P5A-2: Server-side Search Tests

Verifies:
1. GET /api/search/quick returns BM25 keyword search results
2. GET /api/search/resolve-link resolves wiki links server-side
3. GET /api/search/hybrid still works (semantic mode)
"""

import httpx
import asyncio

BASE = "http://localhost:8001"


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        print("=" * 60)
        print("  P5A-2: Server-side Search Tests")
        print("=" * 60)

        errors = []

        # Test 1: Quick search endpoint
        print("\n[Test 1] GET /api/search/quick?q=test")
        r = await client.get("/api/search/quick?q=test&limit=5")
        if r.status_code == 200:
            results = r.json()
            print(f"  Status: 200, Results: {len(results)}")
            if results:
                print(f"  First result: path={results[0]['path']}, score={results[0]['score']}")
            print("  PASS")
        else:
            errors.append(f"Test 1: Expected 200, got {r.status_code}")
            print(f"  FAIL: {r.status_code}")

        # Test 2: Quick search with Korean
        print("\n[Test 2] GET /api/search/quick?q=위키 (Korean)")
        r = await client.get("/api/search/quick?q=위키&limit=5")
        if r.status_code == 200:
            results = r.json()
            print(f"  Status: 200, Results: {len(results)}")
            print("  PASS")
        else:
            errors.append(f"Test 2: Expected 200, got {r.status_code}")

        # Test 3: Quick search - empty query should fail validation
        print("\n[Test 3] GET /api/search/quick without q — validation")
        r = await client.get("/api/search/quick")
        if r.status_code == 422:
            print("  PASS — 422 validation error as expected")
        else:
            errors.append(f"Test 3: Expected 422, got {r.status_code}")

        # Test 4: Resolve link endpoint
        print("\n[Test 4] GET /api/search/resolve-link?target=test")
        r = await client.get("/api/search/resolve-link?target=test")
        if r.status_code == 200:
            data = r.json()
            print(f"  Status: 200, path={data.get('path')}")
            print("  PASS")
        else:
            errors.append(f"Test 4: Expected 200, got {r.status_code}")

        # Test 5: Resolve link with nonexistent target
        print("\n[Test 5] GET /api/search/resolve-link?target=nonexistent_xyz")
        r = await client.get("/api/search/resolve-link?target=nonexistent_xyz_12345")
        if r.status_code == 200:
            data = r.json()
            if data.get("path") is None:
                print("  PASS — returns null path for nonexistent target")
            else:
                errors.append(f"Test 5: Expected null path, got {data['path']}")
        else:
            errors.append(f"Test 5: Expected 200, got {r.status_code}")

        # Test 6: Hybrid search still works
        print("\n[Test 6] GET /api/search/hybrid?q=test (semantic mode)")
        r = await client.get("/api/search/hybrid?q=test&n=5")
        if r.status_code == 200:
            results = r.json()
            print(f"  Status: 200, Results: {len(results)}")
            print("  PASS")
        else:
            errors.append(f"Test 6: Expected 200, got {r.status_code}")

        # Test 7: Quick search response time
        print("\n[Test 7] Quick search response time")
        import time
        start = time.time()
        for _ in range(5):
            await client.get("/api/search/quick?q=test&limit=10")
        elapsed = time.time() - start
        avg_ms = (elapsed / 5) * 1000
        print(f"  5 requests avg: {avg_ms:.0f}ms")
        if avg_ms < 100:
            print("  PASS — under 100ms average")
        else:
            print(f"  WARNING — {avg_ms:.0f}ms (target <100ms)")

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
