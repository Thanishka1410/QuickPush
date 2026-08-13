"""
GitHub REST API integration for QuickPush CLI.
Handles automatic Pull Request creation, Draft PRs, labels, assignees, requested reviewers,
and PR template auto-detection using standard library HTTP client.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List


def detect_pr_template(cwd: Optional[str] = None) -> Optional[str]:
    """
    Auto-detect PR template file in repository (.github/PULL_REQUEST_TEMPLATE.md, etc.).
    Returns template content string if found.
    """
    base_dir = Path(cwd) if cwd else Path.cwd()

    possible_paths = [
        base_dir / ".github" / "PULL_REQUEST_TEMPLATE.md",
        base_dir / ".github" / "pull_request_template.md",
        base_dir / "PULL_REQUEST_TEMPLATE.md",
        base_dir / "pull_request_template.md"
    ]

    for p in possible_paths:
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass

    return None


def add_pr_labels(token: str, owner: str, repo: str, pr_number: int, labels: List[str]) -> bool:
    """Attach labels to a Pull Request issue."""
    if not labels:
        return True

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/labels"
    data_bytes = json.dumps({"labels": labels}).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "QuickPush-CLI"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode() in (200, 201)
    except Exception:
        return False


def add_pr_assignees(token: str, owner: str, repo: str, pr_number: int, assignees: List[str]) -> bool:
    """Assign users to a Pull Request issue."""
    if not assignees:
        return True

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/assignees"
    data_bytes = json.dumps({"assignees": assignees}).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "QuickPush-CLI"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode() in (200, 201)
    except Exception:
        return False


def add_pr_reviewers(token: str, owner: str, repo: str, pr_number: int, reviewers: List[str]) -> bool:
    """Request reviewers for a Pull Request."""
    if not reviewers:
        return True

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers"
    data_bytes = json.dumps({"reviewers": reviewers}).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "QuickPush-CLI"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode() in (200, 201)
    except Exception:
        return False


def create_pull_request(
    token: str,
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str = "main",
    title: Optional[str] = None,
    body: Optional[str] = None,
    draft: bool = False,
    labels: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
    reviewers: Optional[List[str]] = None,
    cwd: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Create a Pull Request on GitHub via REST API.

    POST https://api.github.com/repos/{owner}/{repo}/pulls

    Returns (success: bool, message_or_html_url: str, response_dict: dict)
    """
    if not token:
        return False, "GitHub Access Token is required to create a Pull Request. Run 'gpush setup' or set GITHUB_TOKEN environment variable.", {}

    if not owner or not repo:
        return False, "Repository owner and repo name could not be determined.", {}

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"

    pr_title = title or f"PR: {head_branch} -> {base_branch}"
    
    # Auto-detect template if body is not provided
    template_body = detect_pr_template(cwd=cwd)
    pr_body = body or template_body or f"Automated Pull Request created by QuickPush (`gpush`).\n\n- **Branch**: `{head_branch}`\n- **Base**: `{base_branch}`"

    payload = {
        "title": pr_title,
        "head": head_branch,
        "base": base_branch,
        "body": pr_body,
        "draft": draft,
        "maintainer_can_modify": True
    }

    data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "QuickPush-CLI"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.getcode()
            response_body = resp.read().decode("utf-8")
            res_dict = json.loads(response_body)

            if status_code in (200, 201):
                pr_url = res_dict.get("html_url", "")
                pr_number = res_dict.get("number", 0)

                # Attach extra attributes if provided
                extra_msgs = []
                if labels and pr_number:
                    if add_pr_labels(token, owner, repo, pr_number, labels):
                        extra_msgs.append(f"labels ({', '.join(labels)})")
                if assignees and pr_number:
                    if add_pr_assignees(token, owner, repo, pr_number, assignees):
                        extra_msgs.append(f"assignees ({', '.join(assignees)})")
                if reviewers and pr_number:
                    if add_pr_reviewers(token, owner, repo, pr_number, reviewers):
                        extra_msgs.append(f"reviewers ({', '.join(reviewers)})")

                pr_type = "Draft Pull Request" if draft else "Pull Request"
                msg = f"{pr_type} #{pr_number} created: {pr_url}"
                if extra_msgs:
                    msg += f" with {', '.join(extra_msgs)}"

                return True, msg, res_dict
            
            return False, f"Unexpected response ({status_code}): {response_body}", res_dict

    except urllib.error.HTTPError as e:
        error_content = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(error_content)
            errors = err_json.get("errors", [])
            msg = err_json.get("message", "HTTP Error")
            if errors and isinstance(errors, list) and "message" in errors[0]:
                msg += f" - {errors[0]['message']}"
            return False, f"GitHub API Error ({e.code}): {msg}", err_json
        except Exception:
            return False, f"GitHub API Error ({e.code}): {error_content}", {}

    except urllib.error.URLError as e:
        return False, f"Network Error reaching GitHub API: {e.reason}", {}
    except Exception as e:
        return False, f"An unexpected error occurred: {str(e)}", {}
