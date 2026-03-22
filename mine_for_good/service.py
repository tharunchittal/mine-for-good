"""Background service orchestrator for mine-for-good.

Ties together the activity monitor and the miner process, providing a clean
start/stop interface and an optional daemonisation helper.
"""

import logging
import os
import platform
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from mine_for_good.activity import ActivityMonitor
from mine_for_good.config import load_config
from mine_for_good.miner import MinerProcess, download_xmrig
from mine_for_good.specs import get_specs, print_specs, recommend_threads

logger = logging.getLogger(__name__)

PID_FILE = Path.home() / ".mine-for-good" / "mine-for-good.pid"


class MiningService:
    """
    Orchestrates the miner lifecycle:
    * Downloads XMRig if needed.
    * Starts an ActivityMonitor that starts/stops the miner on idle transitions.
    * Handles OS signals (SIGTERM / SIGINT) for graceful shutdown.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or load_config()
        self._specs = get_specs()
        self._miner: Optional[MinerProcess] = None
        self._monitor: Optional[ActivityMonitor] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Download XMRig if not already present and validate config."""
        wallet = self._config.get("wallet_address", "")
        if not wallet:
            raise ValueError(
                "Wallet address not set. Run 'mine-for-good configure' first."
            )

        xmrig_dir = self._config["mining"]["xmrig_dir"]
        binary_path = download_xmrig(xmrig_dir)

        # Auto-set thread count if not manually configured
        if int(self._config["mining"]["threads"]) <= 0:
            self._config["mining"]["threads"] = recommend_threads(self._specs)

        self._miner = MinerProcess(binary_path, self._config, self._specs)

        activity_cfg = self._config.get("activity", {})
        self._monitor = ActivityMonitor(
            idle_threshold=int(activity_cfg.get("idle_threshold", 60)),
            poll_interval=int(activity_cfg.get("poll_interval", 5)),
            on_idle=self._on_idle,
            on_active=self._on_active,
        )

    def run(self) -> None:
        """Block until a stop signal is received."""
        self._setup_signal_handlers()
        self._write_pid_file()

        print_specs(self._specs)

        logger.info("mine-for-good service starting …")
        self._monitor.start()  # type: ignore[union-attr]

        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=1)
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the service to stop."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Idle / active callbacks
    # ------------------------------------------------------------------

    def _on_idle(self) -> None:
        if self._miner:
            self._miner.start()

    def _on_active(self) -> None:
        if self._miner:
            self._miner.stop()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _shutdown(self) -> None:
        logger.info("Shutting down mine-for-good …")
        if self._monitor:
            self._monitor.stop()
        if self._miner:
            self._miner.stop()
        self._remove_pid_file()
        logger.info("mine-for-good stopped.")

    def _setup_signal_handlers(self) -> None:
        if platform.system() != "Windows":
            signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        logger.info("Received signal %d; stopping …", signum)
        self.stop()

    def _write_pid_file(self) -> None:
        try:
            PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(os.getpid()))
        except OSError as exc:
            logger.warning("Could not write PID file: %s", exc)

    def _remove_pid_file(self) -> None:
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Daemonise helper (Linux / macOS only)
# ---------------------------------------------------------------------------

def daemonise(log_file: Optional[str] = None) -> None:
    """
    Fork the current process into a background daemon (POSIX only).

    After this call, the original parent process exits and the child
    continues running detached from the terminal.
    """
    if platform.system() == "Windows":
        logger.warning("Daemonisation is not supported on Windows. Running in foreground.")
        return

    # First fork
    if os.fork() > 0:
        sys.exit(0)

    os.setsid()

    # Second fork
    if os.fork() > 0:
        sys.exit(0)

    # Redirect stdio
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "r+b") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
        if log_file:
            with open(log_file, "ab") as lf:
                os.dup2(lf.fileno(), sys.stdout.fileno())
                os.dup2(lf.fileno(), sys.stderr.fileno())
        else:
            os.dup2(devnull.fileno(), sys.stdout.fileno())
            os.dup2(devnull.fileno(), sys.stderr.fileno())
