"""Tests for the Tkinter UI config adapter logic."""

import pytest

from mine_for_good.config import load_config
from mine_for_good.ui import update_config_from_form


def test_update_config_from_form_updates_values():
    config = load_config()
    updated = update_config_from_form(
        config,
        {
            "wallet_address": "44abc",
            "worker_name": "laptop-01",
            "idle_threshold": "120",
            "threads": "4",
            "cpu_limit": "60",
        },
    )

    assert updated["wallet_address"] == "44abc"
    assert updated["worker_name"] == "laptop-01"
    assert updated["activity"]["idle_threshold"] == 120
    assert updated["mining"]["threads"] == 4
    assert updated["mining"]["cpu_limit"] == 60


def test_update_config_from_form_rejects_blank_wallet():
    config = load_config()
    with pytest.raises(ValueError, match="Wallet address is required"):
        update_config_from_form(
            config,
            {
                "wallet_address": "",
                "worker_name": "",
                "idle_threshold": "60",
                "threads": "0",
                "cpu_limit": "75",
            },
        )


@pytest.mark.parametrize("field", ["idle_threshold", "threads", "cpu_limit"])
def test_update_config_from_form_rejects_negative_numbers(field):
    config = load_config()
    values = {
        "wallet_address": "44abc",
        "worker_name": "",
        "idle_threshold": "60",
        "threads": "0",
        "cpu_limit": "75",
    }
    values[field] = "-1"

    with pytest.raises(ValueError, match=">= 0"):
        update_config_from_form(config, values)
