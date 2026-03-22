"""Configuration management for mine-for-good."""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "wallet_address": "",
    "pool": {
        "url": "gulf.moneroocean.stream",
        "port": 10128,
        "tls": True,
    },
    "worker_name": "",
    "activity": {
        # Seconds of inactivity before mining resumes
        "idle_threshold": 60,
        # How often (seconds) to check for user activity
        "poll_interval": 5,
    },
    "mining": {
        # Number of CPU threads (0 = auto-detect)
        "threads": 0,
        # CPU usage limit per thread in percent (0 = no limit)
        "cpu_limit": 75,
        # Directory where XMRig binary is stored
        "xmrig_dir": str(Path.home() / ".mine-for-good" / "xmrig"),
    },
    "logging": {
        "level": "INFO",
        "file": str(Path.home() / ".mine-for-good" / "mine-for-good.log"),
    },
}

CONFIG_PATH = Path.home() / ".mine-for-good" / "config.json"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from file, merging with defaults."""
    config_file = Path(path) if path else CONFIG_PATH
    config = _deep_merge({}, DEFAULT_CONFIG)

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as fh:
                user_config = json.load(fh)
            config = _deep_merge(config, user_config)
            logger.debug("Loaded config from %s", config_file)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read config file %s: %s", config_file, exc)
    else:
        logger.info(
            "No config file found at %s; using defaults. "
            "Run 'mine-for-good configure' to set your wallet address.",
            config_file,
        )

    return config


def save_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Persist configuration to file."""
    config_file = Path(path) if path else CONFIG_PATH
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
    logger.info("Config saved to %s", config_file)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def configure_interactive(existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Prompt the user for essential settings and return updated config."""
    config = existing or load_config()

    print("\n=== mine-for-good configuration ===\n")

    wallet = input(
        f"Monero wallet address [{config.get('wallet_address', '')}]: "
    ).strip()
    if wallet:
        config["wallet_address"] = wallet

    worker = input(
        f"Worker name (optional) [{config.get('worker_name', '')}]: "
    ).strip()
    if worker:
        config["worker_name"] = worker

    idle_str = input(
        f"Idle threshold in seconds [{config['activity']['idle_threshold']}]: "
    ).strip()
    if idle_str.isdigit():
        config["activity"]["idle_threshold"] = int(idle_str)

    threads_str = input(
        f"CPU threads (0 = auto) [{config['mining']['threads']}]: "
    ).strip()
    if threads_str.isdigit():
        config["mining"]["threads"] = int(threads_str)

    cpu_limit_str = input(
        f"CPU usage limit per thread % (0 = none) [{config['mining']['cpu_limit']}]: "
    ).strip()
    if cpu_limit_str.isdigit():
        config["mining"]["cpu_limit"] = int(cpu_limit_str)

    save_config(config)
    return config
