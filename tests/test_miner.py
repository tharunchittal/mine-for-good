"""Tests for mine_for_good.miner (offline / unit tests only)."""

import platform
import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mine_for_good.miner import MinerProcess, _build_xmrig_args


FAKE_CONFIG = {
    "wallet_address": "4AdUndXHHZ6cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx3skxNgYeYTRj5UzqtReoS43zbFA9K513oDze1FHVi5fCeAB1",
    "pool": {"url": "gulf.moneroocean.stream", "port": 10128, "tls": True},
    "worker_name": "testworker",
    "mining": {"threads": 2, "cpu_limit": 75},
}

FAKE_SPECS = {
    "hostname": "testhost",
    "cpu": {"physical_cores": 4, "logical_cores": 8},
}


def test_build_xmrig_args_contains_wallet():
    args = _build_xmrig_args(FAKE_CONFIG, FAKE_SPECS)
    assert FAKE_CONFIG["wallet_address"] in args


def test_build_xmrig_args_contains_pool_url():
    args = _build_xmrig_args(FAKE_CONFIG, FAKE_SPECS)
    pool_arg = next((a for a in args if "moneroocean" in a), None)
    assert pool_arg is not None


def test_build_xmrig_args_uses_tls_scheme():
    args = _build_xmrig_args(FAKE_CONFIG, FAKE_SPECS)
    pool_arg = next((a for a in args if "moneroocean" in a), None)
    assert pool_arg.startswith("stratum+tcps://")


def test_build_xmrig_args_no_tls():
    config = {**FAKE_CONFIG, "pool": {"url": "pool.example.com", "port": 3333, "tls": False}}
    args = _build_xmrig_args(config, FAKE_SPECS)
    expected_url = "stratum+tcp://pool.example.com:3333"
    assert expected_url in args


def test_build_xmrig_args_missing_wallet_raises():
    config = {**FAKE_CONFIG, "wallet_address": ""}
    with pytest.raises(ValueError, match="wallet"):
        _build_xmrig_args(config, FAKE_SPECS)


def test_build_xmrig_args_thread_count():
    args = _build_xmrig_args(FAKE_CONFIG, FAKE_SPECS)
    idx = args.index("--threads")
    assert args[idx + 1] == "2"


def test_miner_process_not_running_initially():
    proc = MinerProcess("/fake/xmrig", FAKE_CONFIG, FAKE_SPECS)
    assert not proc.is_running


def test_miner_process_stop_when_not_running_is_safe():
    proc = MinerProcess("/fake/xmrig", FAKE_CONFIG, FAKE_SPECS)
    proc.stop()  # should not raise


def test_miner_process_start_and_stop():
    """Integration-style test: launch a real subprocess (echo) and stop it."""
    if platform.system() == "Windows":
        fake_bin = "cmd"
        fake_args_patch = ["/c", "pause"]
    else:
        fake_bin = "/bin/sh"
        fake_args_patch = ["-c", "sleep 60"]

    proc = MinerProcess(fake_bin, FAKE_CONFIG, FAKE_SPECS)

    with patch("mine_for_good.miner._build_xmrig_args", return_value=fake_args_patch):
        proc.start()
        assert proc.is_running
        proc.stop()
        assert not proc.is_running
