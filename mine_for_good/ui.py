"""Simple desktop UI for editing mine-for-good configuration."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from mine_for_good.config import load_config, save_config


def _parse_non_negative_int(value: str, label: str) -> int:
    text = value.strip()
    if not text:
        raise ValueError(f"{label} is required")
    try:
        parsed = int(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{label} must be >= 0")
    return parsed


def update_config_from_form(config: Dict[str, Any], values: Mapping[str, str]) -> Dict[str, Any]:
    """Apply validated form values to a config dict."""
    wallet = values["wallet_address"].strip()
    if not wallet:
        raise ValueError("Wallet address is required")

    updated = {
        **config,
        "wallet_address": wallet,
        "worker_name": values["worker_name"].strip(),
        "activity": {
            **config["activity"],
            "idle_threshold": _parse_non_negative_int(values["idle_threshold"], "Idle threshold"),
        },
        "mining": {
            **config["mining"],
            "threads": _parse_non_negative_int(values["threads"], "CPU threads"),
            "cpu_limit": _parse_non_negative_int(values["cpu_limit"], "CPU limit"),
        },
    }
    return updated


def configure_with_ui(existing: Optional[Dict[str, Any]] = None) -> bool:
    """Open a small Tkinter form to edit key mining settings.

    Returns True when settings were saved, False when canceled.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError as exc:
        raise RuntimeError("Tkinter is not available in this Python environment") from exc

    config = existing or load_config()
    saved = {"ok": False}

    root = tk.Tk()
    root.title("mine-for-good configuration")
    root.resizable(False, False)
    root.columnconfigure(1, weight=1)

    fields = [
        ("wallet_address", "Monero wallet address", str(config.get("wallet_address", ""))),
        ("worker_name", "Worker name (optional)", str(config.get("worker_name", ""))),
        (
            "idle_threshold",
            "Idle threshold (seconds)",
            str(config["activity"].get("idle_threshold", 60)),
        ),
        ("threads", "CPU threads (0 = auto)", str(config["mining"].get("threads", 0))),
        (
            "cpu_limit",
            "CPU limit per thread % (0 = none)",
            str(config["mining"].get("cpu_limit", 75)),
        ),
    ]

    vars_map: Dict[str, Any] = {}
    for row, (key, label, value) in enumerate(fields):
        tk.Label(root, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        var = tk.StringVar(value=value)
        vars_map[key] = var
        tk.Entry(root, textvariable=var, width=42).grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=6)

    def on_save() -> None:
        values = {k: str(v.get()) for k, v in vars_map.items()}
        try:
            updated = update_config_from_form(config, values)
            save_config(updated)
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=root)
            return

        saved["ok"] = True
        messagebox.showinfo("Saved", "Configuration saved.", parent=root)
        root.destroy()

    def on_cancel() -> None:
        root.destroy()

    button_row = len(fields)
    tk.Button(root, text="Save", command=on_save).grid(
        row=button_row,
        column=0,
        sticky="w",
        padx=12,
        pady=(8, 12),
    )
    tk.Button(root, text="Cancel", command=on_cancel).grid(
        row=button_row,
        column=1,
        sticky="e",
        padx=12,
        pady=(8, 12),
    )

    root.mainloop()
    return bool(saved["ok"])
