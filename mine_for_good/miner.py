"""XMRig downloader and process manager for mine-for-good."""

import logging
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# XMRig GitHub releases API
XMRIG_RELEASES_URL = (
    "https://api.github.com/repos/xmrig/xmrig/releases/latest"
)

# Monero algorithm identifier for XMRig
XMR_ALGO = "rx/0"


def _get_platform_asset_pattern() -> str:
    """Return a pattern matching the correct XMRig release asset for this OS."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if "aarch64" in machine or "arm64" in machine:
            return r"xmrig-.*-linux-static-aarch64\.tar\.gz$"
        return r"xmrig-.*-linux-static-x64\.tar\.gz$"
    if system == "darwin":
        return r"xmrig-.*-macos-arm64\.tar\.gz$" if "arm" in machine else r"xmrig-.*-macos-x64\.tar\.gz$"
    if system == "windows":
        return r"xmrig-.*-msvc-win64\.zip$"
    raise RuntimeError(f"Unsupported platform: {system}")


def download_xmrig(dest_dir: str) -> str:
    """
    Download the latest XMRig release into *dest_dir* and return the path to the
    executable.  Skips download if the binary already exists.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    system = platform.system().lower()
    binary_name = "xmrig.exe" if system == "windows" else "xmrig"
    binary_path = dest / binary_name

    if binary_path.exists():
        logger.info("XMRig already present at %s", binary_path)
        return str(binary_path)

    logger.info("Fetching latest XMRig release information …")
    try:
        req = urllib.request.Request(
            XMRIG_RELEASES_URL,
            headers={"User-Agent": "mine-for-good/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            import json
            release = json.loads(resp.read())
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch XMRig release info: {exc}") from exc

    pattern = _get_platform_asset_pattern()
    asset_url: Optional[str] = None
    asset_name: Optional[str] = None
    for asset in release.get("assets", []):
        if re.search(pattern, asset["name"]):
            asset_url = asset["browser_download_url"]
            asset_name = asset["name"]
            break

    if not asset_url or not asset_name:
        raise RuntimeError(
            f"Could not find a matching XMRig asset for this platform. "
            f"Pattern: {pattern}"
        )

    logger.info("Downloading XMRig from %s …", asset_url)
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, asset_name)
        urllib.request.urlretrieve(asset_url, archive_path)  # noqa: S310

        # Extract
        if asset_name.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(tmpdir)  # noqa: S202
        elif asset_name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(tmpdir)
        else:
            raise RuntimeError(f"Unknown archive format: {asset_name}")

        # Find the binary anywhere in the extracted tree
        for root, _dirs, files in os.walk(tmpdir):
            if binary_name in files:
                extracted_bin = Path(root) / binary_name
                shutil.copy2(extracted_bin, binary_path)
                break
        else:
            raise RuntimeError("XMRig binary not found in downloaded archive.")

    # Make executable on Unix
    if system != "windows":
        binary_path.chmod(binary_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    logger.info("XMRig installed at %s", binary_path)
    return str(binary_path)


def _build_xmrig_args(config: Dict[str, Any], specs: Dict[str, Any]) -> List[str]:
    """Construct the XMRig command-line arguments from our configuration."""
    wallet = config.get("wallet_address", "")
    if not wallet:
        raise ValueError(
            "No wallet address configured. Run 'mine-for-good configure' first."
        )

    pool_cfg = config.get("pool", {})
    pool_url = pool_cfg.get("url", "gulf.moneroocean.stream")
    pool_port = pool_cfg.get("port", 10128)
    tls = pool_cfg.get("tls", True)

    scheme = "stratum+tcps" if tls else "stratum+tcp"
    pool_address = f"{scheme}://{pool_url}:{pool_port}"

    worker = config.get("worker_name") or specs.get("hostname", "worker")

    mining_cfg = config.get("mining", {})
    threads = int(mining_cfg.get("threads", 0))
    cpu_limit = int(mining_cfg.get("cpu_limit", 75))

    from mine_for_good.specs import recommend_threads
    if threads <= 0:
        threads = recommend_threads(specs)

    args = [
        "--algo", XMR_ALGO,
        "--url", pool_address,
        "--user", wallet,
        "--pass", worker,
        "--threads", str(threads),
        "--no-color",
        "--log-file", os.devnull,
    ]

    if 0 < cpu_limit < 100:
        args += ["--cpu-max-threads-hint", str(cpu_limit)]

    return args


class MinerProcess:
    """Manages a single XMRig child process."""

    def __init__(self, binary_path: str, config: Dict[str, Any], specs: Dict[str, Any]) -> None:
        self._binary = binary_path
        self._config = config
        self._specs = specs
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._stdout_thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        """Start the XMRig process if it is not already running."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                logger.debug("Miner already running (pid=%d)", self._proc.pid)
                return

            args = [self._binary] + _build_xmrig_args(self._config, self._specs)
            logger.info("Starting miner: %s", " ".join(args))

            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid if platform.system() != "Windows" else None,
            )
            self._stdout_thread = threading.Thread(
                target=self._log_output, daemon=True
            )
            self._stdout_thread.start()
            logger.info("Miner started (pid=%d)", self._proc.pid)

    def stop(self) -> None:
        """Stop the XMRig process gracefully."""
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                return
            logger.info("Stopping miner (pid=%d) …", self._proc.pid)
            try:
                if platform.system() != "Windows":
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                else:
                    self._proc.terminate()
                self._proc.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass
            self._proc = None
            logger.info("Miner stopped.")

    def _log_output(self) -> None:
        """Forward XMRig stdout to the Python logger."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if line:
                logger.debug("[xmrig] %s", line)
