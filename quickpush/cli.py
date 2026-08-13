"""
Main CLI entry point for QuickPush (`gpush`).
Handles argument parsing, user configuration interactive setup, terminal output formatting,
pre-push safety testing/linting checks, and workflow orchestration for git add, commit, push, PR creation, and AI commit generation.
"""

import argparse
import sys
from typing import List, Optional

from quickpush import __version__
from quickpush.ai_commit import generate_ai_commit_message
from quickpush.checker import detect_test_command, detect_lint_command, run_check
from quickpush.config import load_config, save_config, get_token, get_config_path
from quickpush.git_utils import (
    is_git_repository,
    get_current_branch,
    get_remote_url,
    parse_github_repo_info,
    has_uncommitted_changes,
    has_staged_changes,
    git_add_all,
    git_commit,
    git_push,
    get_default_commit_message
)
from quickpush.github_api import create_pull_request


# Ensure UTF-8 output on Windows consoles if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_symbol(symbol: str, fallback: str) -> str:
    """Return symbol if stdout encoding supports it, else fallback."""
    try:
        symbol.encode(sys.stdout.encoding or "utf-8")
        return symbol
    except (UnicodeEncodeError, AttributeError, TypeError):
        return fallback


# Simple ANSI Color formatting with encoding-safe symbols
class Style:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    ICON_INFO = safe_symbol("ℹ", "[i]")
    ICON_SUCCESS = safe_symbol("✔", "[+]")
    ICON_WARN = safe_symbol("⚠", "[!]")
    ICON_ERROR = safe_symbol("✖", "[x]")
    ICON_ROCKET = safe_symbol("🚀", ">>")
    ICON_SPARKLE = safe_symbol("✨", "*")
    ICON_ROBOT = safe_symbol("🤖", "[AI]")
    ICON_SHIELD = safe_symbol("🛡️", "[SAFETY]")

    @classmethod
    def info(cls, msg: str) -> str:
        return f"{cls.CYAN}{cls.ICON_INFO} {msg}{cls.RESET}"

    @classmethod
    def success(cls, msg: str) -> str:
        return f"{cls.GREEN}{cls.ICON_SUCCESS} {msg}{cls.RESET}"

    @classmethod
    def warn(cls, msg: str) -> str:
        return f"{cls.YELLOW}{cls.ICON_WARN} {msg}{cls.RESET}"

    @classmethod
    def error(cls, msg: str) -> str:
        return f"{cls.RED}{cls.ICON_ERROR} {msg}{cls.RESET}"


def run_setup(
    username: Optional[str],
    repo: Optional[str],
    token: Optional[str],
    branch: Optional[str],
    ai_key: Optional[str] = None,
    ai_provider: Optional[str] = None,
    test_cmd: Optional[str] = None,
    lint_cmd: Optional[str] = None
):
    """Execute the interactive or flagged setup command to update ~/.gpconfig."""
    print(f"\n{Style.BOLD}--- QuickPush Configuration Setup ---{Style.RESET}\n")

    current = load_config()

    if not any([username, repo, token, branch, ai_key, ai_provider, test_cmd, lint_cmd]):
        print("Enter your GitHub configuration options below (press Enter to keep existing value):\n")
        
        user_in = input(f"GitHub Username [{current.get('github_username', '')}]: ").strip()
        username = user_in if user_in else current.get('github_username')

        repo_in = input(f"Default Repo (owner/repo) [{current.get('github_repo', '')}]: ").strip()
        repo = repo_in if repo_in else current.get('github_repo')

        token_in = input(f"GitHub Personal Access Token [{ '******' if current.get('github_token') else '' }]: ").strip()
        token = token_in if token_in else current.get('github_token')

        branch_in = input(f"Default Base Branch [{current.get('default_branch', 'main')}]: ").strip()
        branch = branch_in if branch_in else current.get('default_branch', 'main')

        ai_key_in = input(f"AI API Key (Gemini/OpenAI) [{ '******' if current.get('ai_api_key') else '' }]: ").strip()
        ai_key = ai_key_in if ai_key_in else current.get('ai_api_key')

        test_cmd_in = input(f"Default Test Command [{current.get('test_command', '')}]: ").strip()
        test_cmd = test_cmd_in if test_cmd_in else current.get('test_command')

        lint_cmd_in = input(f"Default Lint Command [{current.get('lint_command', '')}]: ").strip()
        lint_cmd = lint_cmd_in if lint_cmd_in else current.get('lint_command')

    new_config = {}
    if username:
        new_config["github_username"] = username
    if repo:
        new_config["github_repo"] = repo
    if token:
        new_config["github_token"] = token
    if branch:
        new_config["default_branch"] = branch
    if ai_key:
        new_config["ai_api_key"] = ai_key
    if ai_provider:
        new_config["ai_provider"] = ai_provider
    if test_cmd:
        new_config["test_command"] = test_cmd
    if lint_cmd:
        new_config["lint_command"] = lint_cmd

    if save_config(new_config):
        print(f"\n{Style.success(f'Configuration successfully saved to {get_config_path()}')}")
    else:
        print(f"\n{Style.error(f'Failed to save configuration to {get_config_path()}')}")


def run_main_workflow(
    message: Optional[str],
    branch_override: Optional[str],
    repo_override: Optional[str],
    skip_add: bool,
    force: bool,
    create_pr: bool,
    pr_base: Optional[str],
    use_ai: bool,
    run_test: bool,
    run_lint: bool,
    test_cmd_override: Optional[str],
    lint_cmd_override: Optional[str],
    dry_run: bool
):
    """Execute the main stage -> test/lint -> commit -> push -> PR workflow."""
    print(f"\n{Style.BOLD}{Style.ICON_ROCKET} QuickPush ({__version__}){Style.RESET}")

    # 1. Verify Git repository
    if not is_git_repository():
        print(Style.error("Current directory is not a Git repository."))
        sys.exit(1)

    # 2. Determine target branch
    branch = branch_override or get_current_branch()
    if not branch:
        print(Style.error("Could not determine current Git branch. Specify one using --branch <name>."))
        sys.exit(1)
    print(Style.info(f"Target Branch: {Style.BOLD}{branch}{Style.RESET}"))

    # 3. Determine GitHub owner/repo & token
    config = load_config()
    remote_url = get_remote_url("origin")
    owner, repo_name = parse_github_repo_info(remote_url or "")

    if repo_override:
        if "/" in repo_override and not repo_override.startswith("http"):
            parts = repo_override.split("/", 1)
            owner, repo_name = parts[0], parts[1]
        else:
            ov_owner, ov_repo = parse_github_repo_info(repo_override)
            if ov_owner and ov_repo:
                owner, repo_name = ov_owner, ov_repo

    if not owner or not repo_name:
        owner = owner or config.get("github_username")
        repo_name = repo_name or config.get("github_repo")

    if owner and repo_name:
        print(Style.info(f"GitHub Repository: {Style.BOLD}{owner}/{repo_name}{Style.RESET}"))

    # 4. Stage changes (`git add .`)
    if skip_add:
        print(Style.info("Skipping 'git add .' (--skip-add flag provided)."))
    else:
        if dry_run:
            print(Style.info("[DRY RUN] Would execute: git add ."))
        else:
            if has_uncommitted_changes():
                print("Staging all changes...")
                success, msg = git_add_all()
                if not success:
                    print(Style.error(msg))
                    sys.exit(1)
                print(Style.success("Staged changes successfully."))
            else:
                print(Style.info("No uncommitted changes detected to stage."))

    # 4b. Pre-Push Safety Checks (Linting & Testing)
    if run_lint or config.get("auto_lint", False):
        lint_command = lint_cmd_override or config.get("lint_command") or detect_lint_command()
        if not lint_command:
            print(Style.warn("Could not auto-detect a lint command. Specify one using --lint-cmd <cmd>."))
        else:
            print(Style.info(f"{Style.ICON_SHIELD} Running Linter: '{lint_command}'..."))
            if dry_run:
                print(Style.info(f"[DRY RUN] Would execute linter check: {lint_command}"))
            else:
                success, out = run_check(lint_command, label="Linter")
                if not success:
                    print(Style.error(f"Linter failed!\n\n{out}\n"))
                    print(Style.error("Pre-push safety check failed. Aborting commit and push."))
                    sys.exit(1)
                print(Style.success("Linter check passed cleanly."))

    if run_test or config.get("auto_test", False):
        test_command = test_cmd_override or config.get("test_command") or detect_test_command()
        if not test_command:
            print(Style.warn("Could not auto-detect a test command. Specify one using --test-cmd <cmd>."))
        else:
            print(Style.info(f"{Style.ICON_SHIELD} Running Test Suite: '{test_command}'..."))
            if dry_run:
                print(Style.info(f"[DRY RUN] Would execute test suite: {test_command}"))
            else:
                success, out = run_check(test_command, label="Test Suite")
                if not success:
                    print(Style.error(f"Test suite failed!\n\n{out}\n"))
                    print(Style.error("Pre-push safety check failed. Aborting commit and push."))
                    sys.exit(1)
                print(Style.success("Test suite passed cleanly."))

    # 5. Determine Commit Message (AI or User/Default)
    if use_ai or (message is None and config.get("auto_ai", False)):
        print(Style.info(f"{Style.ICON_ROBOT} Generating AI commit message..."))
        commit_msg = generate_ai_commit_message(config=config)
        print(Style.info(f"AI Commit Message: {Style.BOLD}'{commit_msg}'{Style.RESET}"))
    else:
        commit_msg = message or get_default_commit_message()

    # 6. Commit changes
    if dry_run:
        print(Style.info(f"[DRY RUN] Would execute: git commit -m \"{commit_msg}\""))
    else:
        if has_staged_changes():
            print(f"Committing with message: '{commit_msg}'...")
            success, msg = git_commit(commit_msg)
            if not success:
                print(Style.error(msg))
                sys.exit(1)
            print(Style.success("Committed successfully."))
        else:
            print(Style.info("No staged changes to commit. Proceeding to push existing commits."))

    # 7. Push to GitHub
    remote_name = "origin"
    if dry_run:
        push_cmd = f"git push {'--force ' if force else ''}--set-upstream {remote_name} {branch}"
        print(Style.info(f"[DRY RUN] Would execute: {push_cmd}"))
    else:
        print(f"Pushing to {remote_name}/{branch}...")
        success, msg = git_push(remote=remote_name, branch=branch, force=force)
        if not success:
            print(Style.error(f"Push failed: {msg}"))
            sys.exit(1)
        print(Style.success(f"Pushed to GitHub remote '{remote_name}/{branch}' successfully!"))

    # 8. Create Pull Request if requested
    if create_pr:
        token = get_token(config)
        base = pr_base or config.get("default_branch") or "main"

        if dry_run:
            print(Style.info(f"[DRY RUN] Would create Pull Request from '{branch}' to '{base}' on {owner}/{repo_name} via GitHub REST API"))
        else:
            print(f"Creating Pull Request on GitHub ({branch} ➔ {base})...")
            if not token:
                print(Style.warn("GitHub Personal Access Token not found! Cannot create PR automatically."))
                print(Style.warn("Set GITHUB_TOKEN environment variable or run 'gpush setup' to configure your token."))
            elif not owner or not repo_name:
                print(Style.error("Could not determine repository owner/name to create PR."))
            else:
                success, pr_msg, _ = create_pull_request(
                    token=token,
                    owner=owner,
                    repo=repo_name,
                    head_branch=branch,
                    base_branch=base,
                    title=commit_msg or f"PR: {branch} -> {base}"
                )
                if success:
                    print(Style.success(pr_msg))
                else:
                    print(Style.warn(f"Failed to create PR: {pr_msg}"))

    print(f"\n{Style.GREEN}{Style.BOLD}{Style.ICON_SPARKLE} Done!{Style.RESET}\n")


def build_parser() -> argparse.ArgumentParser:
    """Build and configure ArgumentParser for gpush."""
    parser = argparse.ArgumentParser(
        prog="gpush",
        description="QuickPush CLI - Automate git add, commit, push, and GitHub PR creation in a single command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  gpush                          # Stage all, auto-commit with timestamp, and push
  gpush -a                       # Stage all, generate AI commit message, and push
  gpush -t                       # Run pre-push unit tests before committing/pushing
  gpush -l -t                    # Run linter & test suite before pushing
  gpush -a -t -p                 # Run tests + AI commit message + open GitHub PR
  gpush setup                    # Configure default username, repo, token, and test command
"""
    )

    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Commit message. If omitted, a default timestamped message or AI message will be generated."
    )

    parser.add_argument(
        "-m", "--message-flag",
        dest="message_flag",
        metavar="MSG",
        help="Alternative flag to specify commit message."
    )

    parser.add_argument(
        "-a", "--ai",
        action="store_true",
        help="Generate commit message automatically using AI diff analysis."
    )

    parser.add_argument(
        "-t", "--test",
        action="store_true",
        help="Run pre-push unit test suite before committing/pushing."
    )

    parser.add_argument(
        "-l", "--lint",
        action="store_true",
        help="Run pre-push linter / code check before committing/pushing."
    )

    parser.add_argument(
        "--test-cmd",
        metavar="CMD",
        help="Custom test command override (e.g., 'pytest', 'npm test')."
    )

    parser.add_argument(
        "--lint-cmd",
        metavar="CMD",
        help="Custom lint command override (e.g., 'ruff check .', 'npm run lint')."
    )

    parser.add_argument(
        "-b", "--branch",
        metavar="BRANCH",
        help="Target branch to push to (defaults to active branch)."
    )

    parser.add_argument(
        "-r", "--repo",
        metavar="REPO",
        help="Override repository target (URL or owner/repo format)."
    )

    parser.add_argument(
        "-s", "--skip-add",
        action="store_true",
        help="Skip automatic 'git add .' step."
    )

    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force push to the remote branch ('git push --force')."
    )

    parser.add_argument(
        "-p", "--pr",
        action="store_true",
        help="Automatically open a Pull Request on GitHub after pushing."
    )

    parser.add_argument(
        "--base",
        metavar="BASE_BRANCH",
        help="Base branch for Pull Request (defaults to 'main')."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the workflow without executing git commands or API requests."
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"QuickPush CLI version {__version__}"
    )

    return parser


def build_setup_parser() -> argparse.ArgumentParser:
    """Build parser for `gpush setup` subcommand."""
    setup_parser = argparse.ArgumentParser(
        prog="gpush setup",
        description="Configure GitHub username, default repo, token, branch, AI key, and test/lint commands."
    )
    setup_parser.add_argument("-u", "--username", help="GitHub Username")
    setup_parser.add_argument("-r", "--repo", help="Default repository (owner/repo)")
    setup_parser.add_argument("-t", "--token", help="GitHub Personal Access Token (PAT)")
    setup_parser.add_argument("-b", "--branch", help="Default target base branch")
    setup_parser.add_argument("--ai-key", help="AI API Key (Gemini or OpenAI)")
    setup_parser.add_argument("--ai-provider", help="AI Provider (gemini or openai)")
    setup_parser.add_argument("--test-cmd", help="Default test command")
    setup_parser.add_argument("--lint-cmd", help="Default lint command")
    return setup_parser


def main(argv: Optional[List[str]] = None):
    """CLI execution entry point."""
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "setup":
        setup_parser = build_setup_parser()
        args = setup_parser.parse_args(argv[1:])
        run_setup(
            username=args.username,
            repo=args.repo,
            token=args.token,
            branch=args.branch,
            ai_key=args.ai_key,
            ai_provider=args.ai_provider,
            test_cmd=args.test_cmd,
            lint_cmd=args.lint_cmd
        )
    else:
        parser = build_parser()
        args = parser.parse_args(argv)
        commit_msg = args.message or args.message_flag
        run_main_workflow(
            message=commit_msg,
            branch_override=args.branch,
            repo_override=args.repo,
            skip_add=args.skip_add,
            force=args.force,
            create_pr=args.pr,
            pr_base=args.base,
            use_ai=args.ai,
            run_test=args.test,
            run_lint=args.lint,
            test_cmd_override=args.test_cmd,
            lint_cmd_override=args.lint_cmd,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
