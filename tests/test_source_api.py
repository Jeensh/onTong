# tests/test_source_api.py
"""Tests for source file tree API endpoint."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import source_api


@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal Java project structure for testing."""
    java_dir = tmp_path / "scm-demo" / "src" / "main" / "java" / "com" / "ontong" / "scm"
    inv_dir = java_dir / "inventory"
    inv_dir.mkdir(parents=True)
    order_dir = java_dir / "order"
    order_dir.mkdir(parents=True)
    (inv_dir / "SafetyStockCalculator.java").write_text(
        "package com.ontong.scm.inventory;\npublic class SafetyStockCalculator {}\n"
    )
    (inv_dir / "InventoryManager.java").write_text(
        "package com.ontong.scm.inventory;\npublic class InventoryManager {}\n"
    )
    (order_dir / "OrderService.java").write_text(
        "package com.ontong.scm.order;\npublic class OrderService {}\n"
    )
    # Hidden dirs that should be excluded
    git_dir = tmp_path / "scm-demo" / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text("[core]\n")
    # Binary file that should be excluded
    (tmp_path / "scm-demo" / "build.class").write_bytes(b"\x00\x01")
    return tmp_path


@pytest.fixture
def app(sample_repo):
    test_app = FastAPI()
    test_app.include_router(source_api.router)
    source_api.init(repos_dir=sample_repo, neo4j_client=None)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestSourceTreeEndpoint:
    def test_directory_structure(self, client):
        """Tree returns nested directory/file nodes with correct types."""
        resp = client.get("/api/modeling/source/tree/scm-demo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "scm-demo"
        assert data["type"] == "directory"
        assert data["path"] == ""
        # Root should have children
        assert len(data["children"]) > 0
        # src should be a directory child
        src = next((c for c in data["children"] if c["name"] == "src"), None)
        assert src is not None
        assert src["type"] == "directory"

    def test_java_files_present(self, client):
        """All .java files appear in the tree with type 'file'."""
        resp = client.get("/api/modeling/source/tree/scm-demo")
        assert resp.status_code == 200
        data = resp.json()

        # Collect all file names recursively
        files = []

        def collect_files(node):
            if node["type"] == "file":
                files.append(node["name"])
            for child in node.get("children", []):
                collect_files(child)

        collect_files(data)
        assert "SafetyStockCalculator.java" in files
        assert "InventoryManager.java" in files
        assert "OrderService.java" in files

    def test_hidden_dirs_excluded(self, client):
        """Hidden directories like .git are excluded from the tree."""
        resp = client.get("/api/modeling/source/tree/scm-demo")
        assert resp.status_code == 200
        data = resp.json()

        # Collect all node names recursively
        names = []

        def collect_names(node):
            names.append(node["name"])
            for child in node.get("children", []):
                collect_names(child)

        collect_names(data)
        assert ".git" not in names
        # Binary files should also be excluded
        assert "build.class" not in names

    def test_nonexistent_repo_404(self, client):
        """Nonexistent repo returns 404."""
        resp = client.get("/api/modeling/source/tree/nonexistent-repo")
        assert resp.status_code == 404

    def test_path_traversal_rejected(self, client, sample_repo):
        """Path traversal via .. in repo_id is rejected."""
        # Create a directory outside the repos_dir to prove it's not exposed
        outside = sample_repo.parent / "outside-secret"
        outside.mkdir(exist_ok=True)
        (outside / "secret.txt").write_text("sensitive data")

        resp = client.get("/api/modeling/source/tree/../outside-secret")
        assert resp.status_code == 404

    def test_symlinks_excluded(self, client, sample_repo):
        """Symlinks inside a repo are not followed."""
        import os
        repo = sample_repo / "scm-demo"
        os.symlink("/tmp", repo / "symlink-escape")

        resp = client.get("/api/modeling/source/tree/scm-demo")
        data = resp.json()

        names = []
        def collect(node):
            names.append(node["name"])
            for c in node.get("children", []):
                collect(c)
        collect(data)
        assert "symlink-escape" not in names


class TestSourceTreeSorting:
    def test_directories_first_then_alphabetical(self, client):
        """Directories come before files, both sorted alphabetically case-insensitive."""
        resp = client.get("/api/modeling/source/tree/scm-demo")
        assert resp.status_code == 200
        data = resp.json()

        def check_sorting(node):
            children = node.get("children", [])
            if not children:
                return
            dirs = [c for c in children if c["type"] == "directory"]
            files = [c for c in children if c["type"] == "file"]
            # Directories should come first
            dir_count = len(dirs)
            for i, child in enumerate(children):
                if i < dir_count:
                    assert child["type"] == "directory", (
                        f"Expected directory at index {i}, got file '{child['name']}'"
                    )
                else:
                    assert child["type"] == "file", (
                        f"Expected file at index {i}, got directory '{child['name']}'"
                    )
            # Within each group, names should be alphabetically sorted (case-insensitive)
            dir_names = [d["name"].lower() for d in dirs]
            assert dir_names == sorted(dir_names)
            file_names = [f["name"].lower() for f in files]
            assert file_names == sorted(file_names)
            # Recurse
            for child in children:
                check_sorting(child)

        check_sorting(data)
