# tests/test_git_connector.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.modeling.infrastructure.git_connector import GitConnector


class TestGitConnector:
    def setup_method(self):
        self.connector = GitConnector(repos_dir=Path("/tmp/ontong-repos"))

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    def test_clone_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        path = self.connector.clone("https://github.com/test/repo.git", "test-repo")
        assert path == Path("/tmp/ontong-repos/test-repo")
        mock_run.assert_called_once()
        assert "clone" in mock_run.call_args[0][0]

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_pull_existing_repo(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date.")
        result = self.connector.pull("test-repo")
        assert "Already up to date" in result

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_list_java_files(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/Main.java\nsrc/Util.java\n",
        )
        files = self.connector.list_files("test-repo", extension=".java")
        assert len(files) == 2
        assert "src/Main.java" in files

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_diff_returns_changed_files(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="M\tsrc/Main.java\nA\tsrc/New.java\nD\tsrc/Old.java\n",
        )
        diff = self.connector.diff("test-repo", "abc123", "def456")
        assert diff.modified == ["src/Main.java"]
        assert diff.added == ["src/New.java"]
        assert diff.deleted == ["src/Old.java"]
