"""
Pre-Push Safety Checks & Testing for QuickPush CLI.
Detects project frameworks (Python, Node.js, Rust, Go) and executes
test suites and linters prior to committing and pushing code.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


def detect_test_command(cwd: Optional[str] = None) -> Optional[str]:
    """
    Auto-detect the appropriate test command for the current repository.
    Inspects project root files (pyproject.toml, package.json, Cargo.toml, go.mod).
    """
    base_dir = Path(cwd) if cwd else Path.cwd()

    # 1. Python Project
    if (base_dir / "pyproject.toml").exists() or (base_dir / "setup.py").exists():
        if (base_dir / "tests").exists() or (base_dir / "test").exists():
            return "python -m unittest discover tests"
        return "pytest"

    # 2. Node.js Project
    pkg_json = base_dir / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                scripts = data.get("scripts", {})
                if "test" in scripts:
                    return "npm test"
        except Exception:
            return "npm test"

    # 3. Rust Project
    if (base_dir / "Cargo.toml").exists():
        return "cargo test"

    # 4. Go Project
    if (base_dir / "go.mod").exists():
        return "go test ./..."

    return None


def detect_lint_command(cwd: Optional[str] = None) -> Optional[str]:
    """
    Auto-detect the appropriate lint command for the current repository.
    """
    base_dir = Path(cwd) if cwd else Path.cwd()

    # 1. Python Project
    if (base_dir / "pyproject.toml").exists() or (base_dir / "ruff.toml").exists():
        return "ruff check ."
    if (base_dir / ".flake8").exists() or (base_dir / "setup.cfg").exists():
        return "flake8 ."

    # 2. Node.js Project
    pkg_json = base_dir / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                scripts = data.get("scripts", {})
                if "lint" in scripts:
                    return "npm run lint"
        except Exception:
            pass

    # 3. Rust Project
    if (base_dir / "Cargo.toml").exists():
        return "cargo clippy"

    # 4. Go Project
    if (base_dir / "go.mod").exists():
        return "golangci-lint run"

    return None


def run_check(cmd_str: str, label: str = "Safety Check", cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    Execute a test or lint command in shell subprocess.
    Returns (success: bool, output: str).
    """
    if not cmd_str:
        return False, "No command provided for check."

    try:
        process = subprocess.run(
            cmd_str,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd
        )
        success = (process.returncode == 0)
        output = process.stdout.strip() if process.stdout else ""
        return success, output
    except Exception as e:
        return False, f"Error executing {label} ('{cmd_str}'): {str(e)}"
