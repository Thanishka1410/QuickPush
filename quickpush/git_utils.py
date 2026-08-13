"""
Git helper functions for QuickPush CLI.
Handles interaction with the local Git binary, repository status checking,
branch auto-detection, URL parsing, staging, committing, and pushing.
"""

import datetime
import re
import subprocess
from typing import Optional, Tuple, List, Dict, Any


def run_git_command(args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Execute a Git command and return (exit_code, stdout, stderr).
    """
    try:
        process = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd
        )
        return process.returncode, process.stdout.strip(), process.stderr.strip()
    except FileNotFoundError:
        return -1, "", "Git executable not found in PATH. Please install Git."
    except Exception as e:
        return -1, "", str(e)


def is_git_repository(cwd: Optional[str] = None) -> bool:
    """Check if the current directory is inside a Git repository."""
    code, out, _ = run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    return code == 0 and out.lower() == "true"


def get_current_branch(cwd: Optional[str] = None) -> Optional[str]:
    """
    Get the name of the active Git branch.
    Returns fallback branch name if in initial unborn state.
    """
    code, out, _ = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if code == 0 and out and out != "HEAD":
        return out

    # Try symbolic-ref for initial unborn branch
    code_sym, out_sym, _ = run_git_command(["symbolic-ref", "--short", "HEAD"], cwd=cwd)
    if code_sym == 0 and out_sym:
        return out_sym

    # Fallback to configured init.defaultBranch or 'main'
    code_def, out_def, _ = run_git_command(["config", "--get", "init.defaultBranch"], cwd=cwd)
    if code_def == 0 and out_def:
        return out_def

    return "main"


def create_and_checkout_branch(branch_name: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    Create a new branch and checkout (`git checkout -b <branch_name>`).
    If the branch already exists, switch to it (`git checkout <branch_name>`).
    """
    if not branch_name:
        return False, "Branch name is required."

    current = get_current_branch(cwd=cwd)
    if current == branch_name:
        return True, f"Already on branch '{branch_name}'."

    # Try creating new branch first
    code, out, err = run_git_command(["checkout", "-b", branch_name], cwd=cwd)
    if code == 0:
        return True, f"Created and checked out new branch '{branch_name}'."

    # If already exists, switch to it
    code_sw, out_sw, err_sw = run_git_command(["checkout", branch_name], cwd=cwd)
    if code_sw == 0:
        return True, f"Switched to existing branch '{branch_name}'."

    return False, err or err_sw or f"Failed to checkout branch '{branch_name}'."




def get_remote_url(remote_name: str = "origin", cwd: Optional[str] = None) -> Optional[str]:
    """Get the URL for the specified remote (default: origin)."""
    code, out, _ = run_git_command(["config", "--get", f"remote.{remote_name}.url"], cwd=cwd)
    if code == 0 and out:
        return out
    return None


def parse_github_repo_info(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse GitHub owner/user and repository name from SSH or HTTPS URLs.

    Examples:
    - git@github.com:owner/repo.git -> ('owner', 'repo')
    - https://github.com/owner/repo.git -> ('owner', 'repo')
    - https://github.com/owner/repo -> ('owner', 'repo')
    - ssh://git@github.com:22/owner/repo.git -> ('owner', 'repo')
    """
    if not url:
        return None, None

    # Clean trailing slashes or .git extensions
    clean_url = url.rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]

    # Pattern for SSH format: git@github.com:owner/repo
    ssh_match = re.search(r"github\.com[:/]([^/]+)/([^/]+)$", clean_url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # Pattern for HTTPS format: https://github.com/owner/repo
    https_match = re.search(r"https?://(?:[^@]+@)?github\.com/([^/]+)/([^/]+)$", clean_url)
    if https_match:
        return https_match.group(1), https_match.group(2)

    return None, None


def has_uncommitted_changes(cwd: Optional[str] = None) -> bool:
    """Check if there are modified, deleted, or untracked files."""
    code, out, _ = run_git_command(["status", "--porcelain"], cwd=cwd)
    return code == 0 and len(out.strip()) > 0


def has_staged_changes(cwd: Optional[str] = None) -> bool:
    """Check if there are already staged changes ready for commit."""
    code, _, _ = run_git_command(["diff", "--cached", "--quiet"], cwd=cwd)
    # exit code 1 means differences exist in cached index (staged changes)
    return code == 1


def git_add_all(cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Run `git add .` to stage all modified, deleted, and untracked files."""
    code, stdout, stderr = run_git_command(["add", "."], cwd=cwd)
    if code == 0:
        return True, "Successfully staged changes (git add .)"
    return False, f"Failed to stage changes: {stderr or stdout}"


def get_default_commit_message() -> str:
    """Generate a clean default commit message with timestamp."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"Auto-commit: {now_str}"


def git_commit(message: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Run `git commit -m "<message>"`."""
    code, stdout, stderr = run_git_command(["commit", "-m", message], cwd=cwd)
    if code == 0:
        return True, stdout or "Committed changes successfully."
    return False, stderr or stdout or "Failed to commit changes."


def remote_branch_exists(remote: str, branch: str, cwd: Optional[str] = None) -> bool:
    """Check if remote branch exists on the specified remote."""
    code, out, _ = run_git_command(["ls-remote", "--heads", remote, branch], cwd=cwd)
    return code == 0 and len(out.strip()) > 0


def git_push(
    remote: str = "origin",
    branch: Optional[str] = None,
    force: bool = False,
    set_upstream: bool = True,
    cwd: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Run `git push`.
    Automatically includes `--set-upstream` if pushing current branch for the first time.
    """
    if not branch:
        branch = get_current_branch(cwd)
        if not branch:
            return False, "Could not determine current branch to push."

    args = ["push"]
    if force:
        args.append("--force")

    if set_upstream:
        args.extend(["--set-upstream", remote, branch])
    else:
        args.extend([remote, branch])

    code, stdout, stderr = run_git_command(args, cwd=cwd)
    if code == 0:
        msg = stdout or stderr or f"Successfully pushed to {remote}/{branch}"
        return True, msg
    
    # If standard push failed because upstream isn't set, retry with --set-upstream
    if "has no upstream branch" in stderr or "set-upstream" in stderr:
        code_up, stdout_up, stderr_up = run_git_command(["push", "--set-upstream", remote, branch], cwd=cwd)
        if code_up == 0:
            return True, stdout_up or stderr_up or f"Pushed & set upstream to {remote}/{branch}"
        return False, stderr_up or stdout_up

    return False, stderr or stdout or f"Failed to push to {remote}/{branch}"
