"""User-activity detection for mine-for-good.

Monitors keyboard, mouse, and (on Linux) X11/Wayland idle time to decide
whether the machine is in use.  Falls back to a simple psutil-based CPU
heuristic when platform-specific libraries are unavailable.
"""

import logging
import platform
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_system = platform.system()


# ---------------------------------------------------------------------------
# Low-level idle-time helpers
# ---------------------------------------------------------------------------

def _get_idle_seconds_linux() -> Optional[float]:
    """
    Return idle time in seconds using the X11 screensaver extension, or
    *None* if unavailable.
    """
    try:
        # xprintidle reports milliseconds of X11 idle time
        import subprocess
        result = subprocess.run(
            ["xprintidle"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return float(result.stdout.strip()) / 1000.0
    except Exception:
        pass

    # Try python-xlib
    try:
        from Xlib import display as xdisplay
        from Xlib.ext import screensaver

        d = xdisplay.Display()
        root = d.screen().root
        info = screensaver.query_info(root)
        return info.idle / 1000.0
    except Exception:
        pass

    return None


def _get_idle_seconds_macos() -> Optional[float]:
    """Return idle time in seconds on macOS using IOKit."""
    try:
        import subprocess
        result = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if "HIDIdleTime" in line:
                parts = line.split("=")
                if len(parts) >= 2:
                    nanoseconds = int(parts[-1].strip())
                    return nanoseconds / 1_000_000_000.0
    except Exception:
        pass
    return None


def _get_idle_seconds_windows() -> Optional[float]:
    """Return idle time in seconds on Windows using ctypes."""
    try:
        import ctypes
        import ctypes.wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(lii)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    except Exception:
        pass
    return None


def get_idle_seconds() -> float:
    """
    Return the number of seconds the user has been idle.

    Tries platform-native methods first, then falls back to 0 (meaning
    "assume active") so mining is never started when we cannot tell.
    """
    idle: Optional[float] = None

    if _system == "Linux":
        idle = _get_idle_seconds_linux()
    elif _system == "Darwin":
        idle = _get_idle_seconds_macos()
    elif _system == "Windows":
        idle = _get_idle_seconds_windows()

    if idle is None:
        logger.debug(
            "Could not determine idle time on %s; assuming active.", _system
        )
        return 0.0

    return max(0.0, idle)


# ---------------------------------------------------------------------------
# Activity monitor
# ---------------------------------------------------------------------------

class ActivityMonitor:
    """
    Polls user idle time at a configurable interval and invokes callbacks
    when the machine transitions between *active* and *idle* states.

    Parameters
    ----------
    idle_threshold : int
        Seconds of inactivity that count as "idle".
    poll_interval : int
        How frequently (in seconds) to check idle time.
    on_idle : callable
        Called (with no arguments) when the machine becomes idle.
    on_active : callable
        Called (with no arguments) when the machine becomes active again.
    """

    def __init__(
        self,
        idle_threshold: int = 60,
        poll_interval: int = 5,
        on_idle: Optional[Callable[[], None]] = None,
        on_active: Optional[Callable[[], None]] = None,
    ) -> None:
        self._idle_threshold = idle_threshold
        self._poll_interval = poll_interval
        self._on_idle = on_idle or (lambda: None)
        self._on_active = on_active or (lambda: None)
        self._is_idle: Optional[bool] = None  # unknown until first poll
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_idle(self) -> bool:
        """True if the machine is currently considered idle."""
        return bool(self._is_idle)

    def start(self) -> None:
        """Begin polling in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="activity-monitor", daemon=True
        )
        self._thread.start()
        logger.info(
            "Activity monitor started (idle threshold=%ds, poll=%ds)",
            self._idle_threshold,
            self._poll_interval,
        )

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._poll_interval + 2)
        logger.info("Activity monitor stopped.")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                idle_secs = get_idle_seconds()
                currently_idle = idle_secs >= self._idle_threshold

                if currently_idle and not self._is_idle:
                    self._is_idle = True
                    logger.info(
                        "User idle for %.0fs (>= threshold %ds) → starting miner",
                        idle_secs,
                        self._idle_threshold,
                    )
                    self._on_idle()
                elif not currently_idle and self._is_idle is not False:
                    # First poll or transition to active
                    self._is_idle = False
                    logger.info(
                        "User active (idle=%.0fs < threshold %ds) → stopping miner",
                        idle_secs,
                        self._idle_threshold,
                    )
                    self._on_active()
            except Exception as exc:
                logger.warning("Activity monitor error: %s", exc)

            self._stop_event.wait(self._poll_interval)
