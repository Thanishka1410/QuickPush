"""
Config management for QuickPush CLI.
Handles reading, writing, and merging settings stored in ~/.gpconfig.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

CONFIG_FILE_NAME = ".gpconfig"


def get_config_path() -> Path:
    """Return the absolute path to the ~/.gpconfig configuration file."""
    return Path.home() / CONFIG_FILE_NAME


def load_config() -> Dict[str, Any]:
    """
    Load configuration from ~/.gpconfig if it exists.
    Returns a dictionary of configured key-value pairs.
    """
    config_path = get_config_path()
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: Dict[str, Any]) -> bool:
    """
    Save the given configuration dictionary to ~/.gpconfig.
    Returns True on success, False on error.
    """
    config_path = get_config_path()
    try:
        # Read existing to preserve extra fields if any
        existing = load_config()
        existing.update(data)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        return True
    except OSError:
        return False


def get_token(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Retrieve GitHub token with priority:
    1. GITHUB_TOKEN or GH_TOKEN environment variable
    2. ~/.gpconfig token entry
    """
    env_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if env_token:
        return env_token.strip()

    if config is None:
        config = load_config()

    token = config.get("github_token") or config.get("token")
    return token.strip() if token else None


def get_ai_key(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Retrieve AI API key (Gemini/OpenAI) from environment or config."""
    env_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    if config is None:
        config = load_config()

    key = config.get("ai_api_key") or config.get("gemini_api_key") or config.get("openai_api_key")
    return key.strip() if key else None


def get_check_commands(config: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Retrieve test and lint commands from config."""
    if config is None:
        config = load_config()

    test_cmd = config.get("test_command")
    lint_cmd = config.get("lint_command")
    return test_cmd, lint_cmd


