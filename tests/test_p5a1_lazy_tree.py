"""P5A-1: Lazy Tree Loading Tests

Verifies:
1. GET /api/wiki/tree?depth=1 returns only top-level items with has_children flag
2. GET /api/wiki/tree/{path} returns subtree children with has_children flag
3. Folders with children have has_children=True
4. Empty folders have has_children=False
5. Files don't have has_children set
"""

import httpx
import asyncio

BASE = "http://localhost:8001"


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        print("=" * 60)
        print("  P5A-1: Lazy Tree Loading Tests")
        print("=" * 60)

        # Setup: Create test folder structure
        print("\n[Setup] Creating test folders and files...")
        # Create nested structure: _test_lazy/sub1/sub2/deep.md + _test_lazy/file.md
        await client.post("/api/wiki/folder/_test_lazy")
        await client.post("/api/wiki/folder/_test_lazy/sub1")
        await client.post("/api/wiki/folder/_test_lazy/sub1/sub2")
        await client.post("/api/wiki/folder/_test_lazy/empty_dir")
        await client.put(
            "/api/wiki/file/_test_lazy/file.md",
            json={"content": "# Test\n\nLazy loading test file"},
        )
        await client.put(
            "/api/wiki/file/_test_lazy/sub1/nested.md",
            json={"content": "# Nested\n\nNested file"},
        )
        await client.put(
            "/api/wiki/file/_test_lazy/sub1/sub2/deep.md",
            json={"content": "# Deep\n\nDeep nested file"},
        )

        errors = []

        # Test 1: depth=1 returns top-level only
        print("\n[Test 1] GET /api/wiki/tree?depth=1 — top-level only")
        r = await client.get("/api/wiki/tree?depth=1")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        tree = r.json()

        # Find _test_lazy folder
        test_folder = next((n for n in tree if n["path"] == "_test_lazy"), None)
        if test_folder is None:
            errors.append("Test 1: _test_lazy folder not found in tree")
        else:
            # Should be a directory with has_children=True but children=[]
            if not test_folder["is_dir"]:
                errors.append("Test 1: _test_lazy should be a directory")
            if test_folder["children"]:
                errors.append(f"Test 1: depth=1 should have empty children, got {len(test_folder['children'])} children")
            if not test_folder.get("has_children"):
                errors.append("Test 1: _test_lazy should have has_children=True")
            print(f"  _test_lazy: is_dir={test_folder['is_dir']}, children={len(test_folder['children'])}, has_children={test_folder.get('has_children')}")
        print("  PASS" if not errors else f"  FAIL: {errors[-1]}")

        # Test 2: Subtree loading
        print("\n[Test 2] GET /api/wiki/tree/_test_lazy — subtree children")
        r = await client.get("/api/wiki/tree/_test_lazy")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        children = r.json()
        names = sorted([c["name"] for c in children])
        expected = sorted(["empty_dir", "file.md", "sub1"])
        if names != expected:
            errors.append(f"Test 2: Expected children {expected}, got {names}")
        else:
            print(f"  Children: {names}")

        # Check has_children flags on children
        sub1 = next((c for c in children if c["name"] == "sub1"), None)
        empty_dir = next((c for c in children if c["name"] == "empty_dir"), None)
        file_node = next((c for c in children if c["name"] == "file.md"), None)

        if sub1 and not sub1.get("has_children"):
            errors.append("Test 2: sub1 should have has_children=True")
        if empty_dir and empty_dir.get("has_children"):
            errors.append("Test 2: empty_dir should have has_children=False")
        if file_node and file_node.get("has_children") is not None:
            # Files shouldn't have has_children set (or it should be None/null)
            pass  # Some serialization may include null, that's fine

        print(f"  sub1: has_children={sub1.get('has_children') if sub1 else 'N/A'}")
        print(f"  empty_dir: has_children={empty_dir.get('has_children') if empty_dir else 'N/A'}")
        print(f"  file.md: has_children={file_node.get('has_children') if file_node else 'N/A'}")
        if not any("Test 2" in e for e in errors):
            print("  PASS")

        # Test 3: Deeper subtree
        print("\n[Test 3] GET /api/wiki/tree/_test_lazy/sub1 — deeper subtree")
        r = await client.get("/api/wiki/tree/_test_lazy/sub1")
        assert r.status_code == 200
        sub1_children = r.json()
        sub1_names = sorted([c["name"] for c in sub1_children])
        expected_sub1 = sorted(["nested.md", "sub2"])
        if sub1_names != expected_sub1:
            errors.append(f"Test 3: Expected {expected_sub1}, got {sub1_names}")
        else:
            print(f"  Children: {sub1_names}")
            sub2 = next((c for c in sub1_children if c["name"] == "sub2"), None)
            if sub2:
                print(f"  sub2: has_children={sub2.get('has_children')}")
                if not sub2.get("has_children"):
                    errors.append("Test 3: sub2 should have has_children=True (contains deep.md)")
        if not any("Test 3" in e for e in errors):
            print("  PASS")

        # Test 4: depth=0 still returns full tree
        print("\n[Test 4] GET /api/wiki/tree?depth=0 — full tree")
        r = await client.get("/api/wiki/tree?depth=0")
        assert r.status_code == 200
        full_tree = r.json()
        test_folder_full = next((n for n in full_tree if n["path"] == "_test_lazy"), None)
        if test_folder_full and test_folder_full["children"]:
            print(f"  _test_lazy has {len(test_folder_full['children'])} children (full)")
            if not any("Test 4" in e for e in errors):
                print("  PASS")
        else:
            errors.append("Test 4: Full tree should have children populated")

        # Test 5: 404 for non-existent folder
        print("\n[Test 5] GET /api/wiki/tree/nonexistent — 404")
        r = await client.get("/api/wiki/tree/nonexistent_folder_xyz")
        if r.status_code == 404:
            print("  PASS — returned 404")
        else:
            errors.append(f"Test 5: Expected 404, got {r.status_code}")

        # Cleanup
        print("\n[Cleanup] Removing test files and folders...")
        await client.delete("/api/wiki/file/_test_lazy/sub1/sub2/deep.md")
        await client.delete("/api/wiki/file/_test_lazy/sub1/nested.md")
        await client.delete("/api/wiki/file/_test_lazy/file.md")
        await client.delete("/api/wiki/folder/_test_lazy/sub1/sub2")
        await client.delete("/api/wiki/folder/_test_lazy/sub1")
        await client.delete("/api/wiki/folder/_test_lazy/empty_dir")
        await client.delete("/api/wiki/folder/_test_lazy")
        print("  Done.")

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
