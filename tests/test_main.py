"""Tests for mine_for_good CLI (main.py)."""

import sys
from unittest.mock import patch

import pytest

from mine_for_good.main import build_parser


def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_version(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])


def test_parser_configure_subcommand():
    parser = build_parser()
    args = parser.parse_args(["configure"])
    assert args.command == "configure"


def test_parser_configure_ui_subcommand():
    parser = build_parser()
    args = parser.parse_args(["configure-ui"])
    assert args.command == "configure-ui"


def test_parser_specs_subcommand():
    parser = build_parser()
    args = parser.parse_args(["specs"])
    assert args.command == "specs"


def test_parser_start_defaults():
    parser = build_parser()
    args = parser.parse_args(["start"])
    assert args.command == "start"
    assert not args.daemon
    assert args.config is None


def test_parser_start_daemon_flag():
    parser = build_parser()
    args = parser.parse_args(["start", "--daemon"])
    assert args.daemon is True


def test_parser_start_config_flag():
    parser = build_parser()
    args = parser.parse_args(["start", "--config", "/tmp/cfg.json"])
    assert args.config == "/tmp/cfg.json"


def test_parser_stop_subcommand():
    parser = build_parser()
    args = parser.parse_args(["stop"])
    assert args.command == "stop"


def test_parser_status_subcommand():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_cmd_specs_runs(capsys):
    from mine_for_good.main import cmd_specs
    import argparse
    cmd_specs(argparse.Namespace())
    captured = capsys.readouterr()
    assert "CPU" in captured.out
