"""Tests for mine_for_good.activity."""

import time
import threading

import pytest

from mine_for_good.activity import ActivityMonitor, get_idle_seconds


def test_get_idle_seconds_returns_non_negative_float():
    result = get_idle_seconds()
    assert isinstance(result, float)
    assert result >= 0.0


def test_activity_monitor_calls_on_active_when_not_idle():
    """When idle_threshold is very large, first poll should report active."""
    active_called = threading.Event()
    idle_called = threading.Event()

    monitor = ActivityMonitor(
        idle_threshold=99999,  # very high – machine won't be this idle
        poll_interval=1,
        on_idle=lambda: idle_called.set(),
        on_active=lambda: active_called.set(),
    )
    monitor.start()
    # Give the monitor time to fire at least one poll
    active_called.wait(timeout=5)
    monitor.stop()

    assert active_called.is_set(), "on_active should have been called"
    assert not idle_called.is_set(), "on_idle should NOT have been called"


def test_activity_monitor_calls_on_idle_when_threshold_is_zero():
    """When idle_threshold is 0, every poll should report idle."""
    idle_called = threading.Event()

    monitor = ActivityMonitor(
        idle_threshold=0,
        poll_interval=1,
        on_idle=lambda: idle_called.set(),
    )
    monitor.start()
    idle_called.wait(timeout=5)
    monitor.stop()

    assert idle_called.is_set(), "on_idle should have been called"


def test_activity_monitor_stop_is_idempotent():
    monitor = ActivityMonitor(idle_threshold=9999, poll_interval=1)
    monitor.start()
    monitor.stop()
    monitor.stop()  # second stop should not raise


def test_activity_monitor_start_is_idempotent():
    monitor = ActivityMonitor(idle_threshold=9999, poll_interval=1)
    monitor.start()
    monitor.start()  # second start should not raise or create extra thread
    monitor.stop()
