"""
AI-Powered Commit Message Generation for QuickPush CLI.
Generates conventional commit messages by analyzing git diffs using
cloud LLM REST APIs (Gemini/OpenAI) or a smart local heuristic engine.
"""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from quickpush.git_utils import run_git_command


def get_staged_diff(cwd: Optional[str] = None, max_lines: int = 200) -> str:
    """
    Retrieve git diff for staged changes.
    Truncates diff if it exceeds max_lines to optimize API token usage.
    """
    code, out, _ = run_git_command(["diff", "--staged"], cwd=cwd)
    if code != 0 or not out.strip():
        # Fallback to unstaged diff if nothing is staged yet
        code, out, _ = run_git_command(["diff", "HEAD"], cwd=cwd)

    if not out.strip():
        return ""

    lines = out.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... (truncated {len(lines) - max_lines} lines)"]

    return "\n".join(lines)


def clean_commit_message(msg: str) -> str:
    """Clean up AI response string (remove quotes, markdown code blocks, trailing periods)."""
    cleaned = msg.strip()
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```$", "", cleaned)
    cleaned = cleaned.strip()

    # Strip surrounding quotes
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()

    # Take only the first line if multiple lines returned
    cleaned = cleaned.splitlines()[0].strip()

    # Remove trailing period if present in conventional commit title
    if cleaned.endswith(".") and not cleaned.endswith("..."):
        cleaned = cleaned[:-1]

    return cleaned


def generate_heuristic_commit_message(cwd: Optional[str] = None) -> str:
    """
    Rule-based conventional commit message generator.
    Analyzes git status output (modified, added, deleted files) to infer scope and type.
    """
    code, out, _ = run_git_command(["status", "--porcelain"], cwd=cwd)
    if code != 0 or not out.strip():
        return "chore: update codebase"

    lines = out.strip().splitlines()
    files_info: List[Tuple[str, str]] = []  # (status, filename)

    for line in lines:
        if len(line) >= 3:
            st = line[:2].strip()
            fname = line[3:].strip()
            files_info.append((st, fname))

    if not files_info:
        return "chore: update codebase"

    file_paths = [Path(fname) for _, fname in files_info]
    exts = {p.suffix.lower() for p in file_paths if p.suffix}
    basenames = [p.name.lower() for p in file_paths]
    stem_names = [p.stem.lower() for p in file_paths]

    # Detect commit type
    commit_type = "feat"
    if all(b in ("readme.md", "license", "changelog.md") or p.suffix.lower() in (".md", ".txt", ".rst") for b, p in zip(basenames, file_paths)):
        commit_type = "docs"
    elif all("test" in b or p.parent.name == "tests" for b, p in zip(basenames, file_paths)):
        commit_type = "test"
    elif all(b in ("pyproject.toml", "package.json", "setup.py", "requirements.txt", ".gitignore") for b in basenames):
        commit_type = "chore"
    elif any(st in ("D", "RM") for st, _ in files_info):
        commit_type = "refactor"
    elif any("fix" in b or "bug" in b for b in basenames):
        commit_type = "fix"

    # Detect scope
    scope = ""
    first_stem = stem_names[0] if stem_names else ""
    if first_stem and first_stem not in ("index", "main", "cli", "__init__"):
        scope = first_stem
    elif file_paths[0].parent.name and file_paths[0].parent.name not in (".", ""):
        scope = file_paths[0].parent.name

    scope_str = f"({scope})" if scope else ""

    # Action summary
    if len(files_info) == 1:
        fname = file_paths[0].name
        st = files_info[0][0]
        action = "add" if "A" in st or "?" in st else "update"
        return f"{commit_type}{scope_str}: {action} {fname}"

    main_files = [p.name for p in file_paths[:2]]
    files_summary = ", ".join(main_files)
    if len(file_paths) > 2:
        files_summary += f" and {len(file_paths) - 2} other files"

    return f"{commit_type}{scope_str}: update {files_summary}"


def generate_api_commit_message(diff_text: str, config: Dict[str, Any]) -> Optional[str]:
    """
    Call cloud LLM REST API (Gemini or OpenAI) to generate a commit message from diff_text.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or config.get("gemini_api_key") or config.get("ai_api_key")
    openai_key = os.getenv("OPENAI_API_KEY") or config.get("openai_api_key")

    provider = config.get("ai_provider", "gemini" if gemini_key else ("openai" if openai_key else None))

    system_prompt = (
        "You are an expert Git assistant. Generate a single-line Conventional Commit message "
        "(e.g., 'feat(auth): add JWT refresh logic' or 'fix(cli): resolve argument parser error') "
        "based on the following git diff. Output ONLY the raw commit message. Do not use quotes or explanation."
    )

    # 1. Gemini REST API
    if provider == "gemini" or gemini_key:
        api_key = gemini_key
        if not api_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\nGit Diff:\n{diff_text}"}
                    ]
                }
            ]
        }
        try:
            req = urllib.request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return clean_commit_message(parts[0].get("text", ""))
        except Exception:
            pass

    # 2. OpenAI REST API
    if provider == "openai" or openai_key:
        api_key = openai_key
        if not api_key:
            return None

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": config.get("ai_model", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Git Diff:\n{diff_text}"}
            ],
            "temperature": 0.2
        }
        try:
            req = urllib.request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return clean_commit_message(content)
        except Exception:
            pass

    return None


def generate_ai_commit_message(cwd: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> str:
    """
    Main function to generate an AI commit message.
    Tries Cloud LLM API if key is present, otherwise falls back to smart local heuristic generator.
    """
    if config is None:
        config = {}

    diff_text = get_staged_diff(cwd=cwd)
    
    if diff_text:
        api_msg = generate_api_commit_message(diff_text, config)
        if api_msg:
            return api_msg

    # Fallback to local heuristic conventional commit engine
    return generate_heuristic_commit_message(cwd=cwd)
