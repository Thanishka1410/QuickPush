"""
Unit tests for QuickPush CLI (`gpush`).
Tests git helper functions, URL parsers, config load/save, and CLI options.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from quickpush.ai_commit import clean_commit_message, generate_heuristic_commit_message
from quickpush.checker import detect_test_command, detect_lint_command, run_check
from quickpush.config import save_config, load_config, get_token, get_config_path
from quickpush.git_utils import parse_github_repo_info, get_default_commit_message
from quickpush.github_api import create_pull_request, detect_pr_template


class TestQuickPush(unittest.TestCase):

    def test_detect_pr_template_none(self):
        """Test PR template detection when no template file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template = detect_pr_template(cwd=tmpdir)
            self.assertIsNone(template)

    def test_detect_pr_template_found(self):
        """Test PR template detection when .github/PULL_REQUEST_TEMPLATE.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gh_dir = Path(tmpdir) / ".github"
            gh_dir.mkdir()
            tmpl_file = gh_dir / "PULL_REQUEST_TEMPLATE.md"
            tmpl_file.write_text("## Description\nMy PR template body", encoding="utf-8")

            template = detect_pr_template(cwd=tmpdir)
            self.assertIsNotNone(template)
            self.assertIn("My PR template body", template)

    def test_detect_test_command(self):
        """Test auto-detecting test command in Python project."""
        cmd = detect_test_command()
        self.assertIsNotNone(cmd)
        self.assertTrue("pytest" in cmd or "unittest" in cmd)


    def test_run_check_success_and_failure(self):
        """Test executing successful and failing commands in run_check."""
        success, out = run_check("python -c \"print('OK')\"")
        self.assertTrue(success)
        self.assertIn("OK", out)

        fail_success, fail_out = run_check("python -c \"import sys; sys.exit(1)\"")
        self.assertFalse(fail_success)

    def test_clean_commit_message(self):
        """Test AI commit message cleaning (markdown block removal, quotes removal)."""
        raw = "```\nfeat(cli): add AI commit flag\n```"
        self.assertEqual(clean_commit_message(raw), "feat(cli): add AI commit flag")

        quoted = '"fix(auth): fix token expiration"'
        self.assertEqual(clean_commit_message(quoted), "fix(auth): fix token expiration")


    def test_heuristic_commit_message(self):
        """Test rule-based conventional commit generator."""
        msg = generate_heuristic_commit_message()
        self.assertTrue(any(msg.startswith(prefix) for prefix in ("feat", "fix", "docs", "chore", "test", "refactor")))

    def test_parse_github_repo_info_ssh(self):

        """Test parsing owner and repo from SSH URLs."""
        url = "git@github.com:torvalds/linux.git"
        owner, repo = parse_github_repo_info(url)
        self.assertEqual(owner, "torvalds")
        self.assertEqual(repo, "linux")

    def test_parse_github_repo_info_https(self):
        """Test parsing owner and repo from HTTPS URLs."""
        url = "https://github.com/psf/black.git"
        owner, repo = parse_github_repo_info(url)
        self.assertEqual(owner, "psf")
        self.assertEqual(repo, "black")

        url_no_git = "https://github.com/psf/black"
        owner, repo = parse_github_repo_info(url_no_git)
        self.assertEqual(owner, "psf")
        self.assertEqual(repo, "black")

    def test_get_default_commit_message(self):
        """Test default timestamp commit message format."""
        msg = get_default_commit_message()
        self.assertTrue(msg.startswith("Auto-commit:"))

    def test_config_load_and_save(self):
        """Test writing and reading from temporary configuration file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_config_file = Path(tmpdir) / ".gpconfig"
            
            # Monkeypatch get_config_path for testing
            original_func = get_config_path
            import quickpush.config
            quickpush.config.get_config_path = lambda: temp_config_file

            try:
                test_data = {
                    "github_username": "octocat",
                    "github_repo": "octocat/Hello-World",
                    "github_token": "ghp_mocktoken123"
                }
                save_res = save_config(test_data)
                self.assertTrue(save_res)

                loaded = load_config()
                self.assertEqual(loaded.get("github_username"), "octocat")
                self.assertEqual(loaded.get("github_token"), "ghp_mocktoken123")

                token = get_token(loaded)
                self.assertEqual(token, "ghp_mocktoken123")

            finally:
                quickpush.config.get_config_path = original_func

    def test_github_pr_missing_token(self):
        """Test PR creation fails gracefully when token is missing."""
        success, msg, _ = create_pull_request(
            token="",
            owner="octocat",
            repo="Hello-World",
            head_branch="feature-x"
        )
        self.assertFalse(success)
        self.assertIn("Token is required", msg)


if __name__ == "__main__":
    unittest.main()
