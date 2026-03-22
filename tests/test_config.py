"""Tests for mine_for_good.config."""

import json
import tempfile
from pathlib import Path

import pytest

from mine_for_good.config import (
    DEFAULT_CONFIG,
    _deep_merge,
    load_config,
    save_config,
)


def test_default_config_has_required_keys():
    assert "wallet_address" in DEFAULT_CONFIG
    assert "pool" in DEFAULT_CONFIG
    assert "activity" in DEFAULT_CONFIG
    assert "mining" in DEFAULT_CONFIG
    assert "logging" in DEFAULT_CONFIG


def test_deep_merge_overrides_values():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}}
    result = _deep_merge(base, override)
    assert result["a"] == 1
    assert result["b"]["c"] == 99
    assert result["b"]["d"] == 3


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    override = {"a": {"x": 2}}
    _deep_merge(base, override)
    assert base["a"]["x"] == 1


def test_load_config_returns_defaults_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        missing = Path(tmpdir) / "nonexistent.json"
        config = load_config(missing)
    # Should still have default keys
    assert "wallet_address" in config
    assert config["activity"]["idle_threshold"] == DEFAULT_CONFIG["activity"]["idle_threshold"]


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"
        original = {"wallet_address": "WALLET123", "activity": {"idle_threshold": 120}}
        save_config(original, path)
        loaded = load_config(path)
    assert loaded["wallet_address"] == "WALLET123"
    assert loaded["activity"]["idle_threshold"] == 120


def test_load_config_ignores_invalid_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "bad.json"
        path.write_text("not valid json{{{")
        config = load_config(path)
    # Should fall back to defaults
    assert "wallet_address" in config
