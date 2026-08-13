# QuickPush (`gpush`) 🚀

A modern, light-weight command-line application that automates staging, committing, pushing code to GitHub, and opening Pull Requests with **a single command**.

---

## Features

- ⚡ **One-Command Workflow**: Replaces `git add .`, `git commit -m "..."`, and `git push` with a single command (`gpush`).
- 🤖 **Auto-Branch & Repo Detection**: Automatically detects active git branch and GitHub remote target (`owner/repo`) from `.git/config`.
- 🔑 **Existing Auth Integration**: Leverages existing Git authentication (SSH keys, Git Credential Manager, Personal Access Tokens) seamlessly without prompting for credentials repeatedly.
- ⚙️ **Persistent Config (`gpush setup`)**: Store your GitHub username, default repo, default base branch, and GitHub Personal Access Token once in `~/.gpconfig`.
- 🔀 **Pull Request Automation (`--pr`)**: Automatically open a GitHub Pull Request for your branch via the GitHub REST API upon pushing.
- 🛡️ **Safe Dry Run (`--dry-run`)**: Preview the exact git commands and API actions before execution.
- 🎨 **Rich Output**: Clean, colorized status output with actionable warnings and error diagnostics.

---

## Project Structure

```
quickpush/
├── pyproject.toml             # Package metadata & CLI entry points
├── README.md                  # Complete documentation and usage examples
├── LICENSE                    # MIT License
├── quickpush/
│   ├── __init__.py            # Package initialization & version info
│   ├── cli.py                 # Main CLI engine, argument parsing & workflow
│   ├── config.py              # Configuration manager (~/.gpconfig)
│   ├── git_utils.py           # Subprocess wrapper for git commands & status check
│   └── github_api.py          # GitHub REST API client for Pull Request creation
└── tests/
    └── test_cli.py            # Unit tests for CLI, URL parsing & config logic
```

---

## Installation Steps

### Option A: Install locally via `pip` (Python 3.8+)

1. Clone or download the repository directory.
2. Navigate to the project root directory:
   ```bash
   cd quickpush
   ```
3. Install in editable mode:
   ```bash
   pip install -e .
   ```

Now the `gpush` and `quickpush` commands are globally accessible in your shell!

### Option B: Install via `pipx` (Recommended for isolated CLI tools)

```bash
pipx install .
```

---

## Quick Start & Setup

### 1. Configure QuickPush (Optional but recommended)

Run `gpush setup` to configure your defaults once:

```bash
gpush setup
```

Or set properties non-interactively using flags:

```bash
gpush setup --username octocat --repo octocat/Hello-World --token ghp_yourPersonalAccessToken123
```

This configuration will be safely stored in `~/.gpconfig` (JSON format):
```json
{
  "github_username": "octocat",
  "github_repo": "octocat/Hello-World",
  "github_token": "ghp_yourPersonalAccessToken123",
  "default_branch": "main"
}
```

---

## Usage Examples

### Standard Push (Default Auto-Commit)
Stage all changes (`git add .`), generate a default commit message with timestamp (`Auto-commit: YYYY-MM-DD HH:MM:SS`), and push to the active branch on GitHub:

```bash
gpush
```

### Custom Commit Message
Pass your commit message directly as an argument:

```bash
gpush "feat: add user authentication endpoint"
```

Or use the `-m` flag:
```bash
gpush -m "fix: resolve memory leak in worker pool"
```

### Create a GitHub Pull Request Automatically
Push code and instantly open a Pull Request against the default base branch (`main`):

```bash
gpush "feat: implement dark mode UI" --pr
```

Specify a custom base branch for the PR:
```bash
gpush "feat: experimental search" --pr --base staging
```

### Override Branch or Remote Repo
Push current local changes to a different branch or remote repository:

```bash
gpush "hotfix: urgent security patch" --branch hotfix-v1.2 --force
```

Override repository target:
```bash
gpush -r "myorg/custom-repo" -m "update docs"
```

### Skip `git add .` (Push existing commits)
If you already staged specific files or made local commits manually, skip `git add .`:

```bash
gpush --skip-add -m "pushing prepared commit"
```

### Dry Run (Preview Mode)
Simulate the full workflow without modifying files or making network requests:

```bash
gpush "test commit" --pr --dry-run
```

Output:
```text
🚀 QuickPush (1.0.0)
ℹ Target Branch: feature/auth
ℹ GitHub Repository: octocat/Hello-World
ℹ [DRY RUN] Would execute: git add .
ℹ [DRY RUN] Would execute: git commit -m "test commit"
ℹ [DRY RUN] Would execute: git push --set-upstream origin feature/auth
ℹ [DRY RUN] Would create Pull Request from 'feature/auth' to 'main' on octocat/Hello-World via GitHub REST API

✨ Done!
```

### AI-Generated Commit Messages (`gpush -a`)
Automatically inspect your staged changes and generate a Conventional Commit message using AI:

```bash
gpush -a
```

### Pre-Push Safety Checks & Testing (`gpush -t` / `gpush -l`)
Run unit tests or linting checks before committing and pushing. If tests or linting fail, execution aborts to prevent broken code from landing on remote:

```bash
# Run unit tests before pushing
gpush -t

# Run linter + unit tests + AI commit message + open PR
gpush -l -t -a -p

# Use custom test/lint command override
gpush --test-cmd "npm test" --lint-cmd "npm run lint"
```

> **Note on AI Keys**: `gpush` includes a built-in smart diff analyzer that works out of the box with zero setup. To use Gemini or OpenAI cloud models, configure your key once via `gpush setup --ai-key YOUR_API_KEY` or export `GEMINI_API_KEY` / `OPENAI_API_KEY` in your environment.

---

## Command Reference

| Flag / Option | Short | Description |
| :--- | :--- | :--- |
| `[MESSAGE]` | | Commit message string (positional argument) |
| `-m`, `--message-flag` | `-m` | Explicit commit message option |
| `-a`, `--ai` | `-a` | Automatically generate Conventional Commit message using AI |
| `-t`, `--test` | `-t` | Run pre-push unit test suite before committing/pushing |
| `-l`, `--lint` | `-l` | Run pre-push linter check before committing/pushing |
| `--test-cmd` | | Custom test command override (e.g. `pytest`, `npm test`) |
| `--lint-cmd` | | Custom lint command override (e.g. `ruff check .`, `npm run lint`) |
| `-b`, `--branch` | `-b` | Target branch to push to (defaults to active branch) |
| `-r`, `--repo` | `-r` | Override repository target (URL or `owner/repo`) |
| `-s`, `--skip-add` | `-s` | Skip standard `git add .` step |
| `-f`, `--force` | `-f` | Perform force push (`git push --force`) |
| `-p`, `--pr` | `-p` | Create a Pull Request on GitHub via API after push |
| `--base` | | Target base branch for PR (default: `main`) |
| `--dry-run` | | Preview actions without executing commands |
| `-v`, `--version` | `-v` | Show QuickPush version |
| `-h`, `--help` | `-h` | Show CLI help manual |



---

## Running Tests

To run the automated test suite:

```bash
python -m unittest discover tests
```

---

## License

This project is open-source under the [MIT License](LICENSE).
