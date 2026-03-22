"""System specification discovery for mine-for-good."""

import logging
import multiprocessing
import os
import platform
import socket
from typing import Any, Dict, Optional

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

try:
    import cpuinfo
    _CPUINFO_AVAILABLE = True
except ImportError:
    _CPUINFO_AVAILABLE = False

logger = logging.getLogger(__name__)


def get_specs() -> Dict[str, Any]:
    """Return a dictionary describing the current machine's specifications."""
    specs: Dict[str, Any] = {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "disk": _get_disk_info(),
    }
    return specs


def _get_cpu_info() -> Dict[str, Any]:
    cpu: Dict[str, Any] = {
        "physical_cores": multiprocessing.cpu_count(),
        "logical_cores": multiprocessing.cpu_count(),
        "name": "Unknown",
        "frequency_mhz": None,
        "has_aes": False,
        "has_avx2": False,
    }

    if _PSUTIL_AVAILABLE:
        try:
            cpu["physical_cores"] = psutil.cpu_count(logical=False) or cpu["physical_cores"]
            cpu["logical_cores"] = psutil.cpu_count(logical=True) or cpu["logical_cores"]
            freq = psutil.cpu_freq()
            if freq:
                cpu["frequency_mhz"] = round(freq.max or freq.current, 1)
        except Exception as exc:
            logger.debug("psutil cpu error: %s", exc)

    if _CPUINFO_AVAILABLE:
        try:
            info = cpuinfo.get_cpu_info()
            cpu["name"] = info.get("brand_raw", cpu["name"])
            flags = info.get("flags", [])
            cpu["has_aes"] = "aes" in flags
            cpu["has_avx2"] = "avx2" in flags
        except Exception as exc:
            logger.debug("cpuinfo error: %s", exc)

    return cpu


def _get_memory_info() -> Dict[str, Any]:
    mem: Dict[str, Any] = {"total_mb": None, "available_mb": None}
    if _PSUTIL_AVAILABLE:
        try:
            vm = psutil.virtual_memory()
            mem["total_mb"] = round(vm.total / 1024 / 1024, 1)
            mem["available_mb"] = round(vm.available / 1024 / 1024, 1)
        except Exception as exc:
            logger.debug("psutil memory error: %s", exc)
    return mem


def _get_disk_info() -> Dict[str, Any]:
    disk: Dict[str, Any] = {"free_gb": None}
    if _PSUTIL_AVAILABLE:
        try:
            usage = psutil.disk_usage(os.path.expanduser("~"))
            disk["free_gb"] = round(usage.free / 1024 / 1024 / 1024, 2)
        except Exception as exc:
            logger.debug("psutil disk error: %s", exc)
    return disk


def recommend_threads(specs: Optional[Dict[str, Any]] = None) -> int:
    """
    Suggest a safe number of mining threads based on available CPU cores.

    Leaves at least one logical core free for the OS / user tasks.
    """
    if specs is None:
        specs = get_specs()

    logical = specs["cpu"].get("logical_cores", 1)
    physical = specs["cpu"].get("physical_cores", 1)

    # Use physical cores minus one, but at least 1
    threads = max(1, physical - 1)
    # Never exceed logical core count
    threads = min(threads, logical)
    return threads


def print_specs(specs: Optional[Dict[str, Any]] = None) -> None:
    """Pretty-print system specifications to stdout."""
    if specs is None:
        specs = get_specs()

    cpu = specs["cpu"]
    mem = specs["memory"]

    print("\n=== System Specifications ===")
    print(f"  Hostname   : {specs['hostname']}")
    print(f"  OS         : {specs['platform']} {specs['platform_version']}")
    print(f"  Architecture: {specs['architecture']}")
    print(f"  CPU        : {cpu['name']}")
    print(f"  Cores      : {cpu['physical_cores']} physical / {cpu['logical_cores']} logical")
    if cpu["frequency_mhz"]:
        print(f"  Freq       : {cpu['frequency_mhz']} MHz")
    print(f"  AES-NI     : {'yes' if cpu['has_aes'] else 'no'}")
    print(f"  AVX2       : {'yes' if cpu['has_avx2'] else 'no'}")
    if mem["total_mb"] is not None:
        print(f"  RAM        : {mem['total_mb']} MB total / {mem['available_mb']} MB free")
    print(f"  Recommended mining threads: {recommend_threads(specs)}")
    print()
