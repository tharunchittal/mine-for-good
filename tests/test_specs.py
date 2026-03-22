"""Tests for mine_for_good.specs."""

import pytest

from mine_for_good.specs import get_specs, recommend_threads


def test_get_specs_returns_expected_keys():
    specs = get_specs()
    assert "hostname" in specs
    assert "platform" in specs
    assert "cpu" in specs
    assert "memory" in specs
    assert "disk" in specs


def test_cpu_info_has_cores():
    specs = get_specs()
    cpu = specs["cpu"]
    assert cpu["logical_cores"] >= 1
    assert cpu["physical_cores"] >= 1


def test_recommend_threads_at_least_one():
    specs = get_specs()
    threads = recommend_threads(specs)
    assert threads >= 1


def test_recommend_threads_does_not_exceed_logical_cores():
    specs = get_specs()
    threads = recommend_threads(specs)
    assert threads <= specs["cpu"]["logical_cores"]


def test_recommend_threads_with_minimal_spec():
    fake_specs = {"cpu": {"physical_cores": 1, "logical_cores": 1}}
    assert recommend_threads(fake_specs) == 1


def test_recommend_threads_leaves_core_free():
    fake_specs = {"cpu": {"physical_cores": 4, "logical_cores": 8}}
    threads = recommend_threads(fake_specs)
    # Should be physical - 1 = 3, which is < logical (8)
    assert threads == 3
