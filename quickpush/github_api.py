"""
GitHub REST API integration for QuickPush CLI.
Handles automatic Pull Request creation using standard library HTTP client.
"""

import json
import urllib.error
import urllib.request
from typing import Tuple, Dict, Any, Optional


def create_pull_request(
    token: str,
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str = "main",
    title: Optional[str] = None,
    body: Optional[str] = None
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
    pr_body = body or f"Automated Pull Request created by QuickPush (`gpush`).\n\n- **Branch**: `{head_branch}`\n- **Base**: `{base_branch}`"

    payload = {
        "title": pr_title,
        "head": head_branch,
        "base": base_branch,
        "body": pr_body,
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
                pr_number = res_dict.get("number", "")
                return True, f"Pull Request #{pr_number} created: {pr_url}", res_dict
            
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
