# mine-for-good

A background Monero (XMR) CPU miner that **automatically pauses while you use
your computer** and resumes the moment you step away.

- Discovers your machine's specifications (CPU cores, frequency, AES-NI, AVX2,
  RAM) and selects a safe thread count automatically.
- Downloads and manages [XMRig](https://xmrig.com/) – the most efficient
  open-source Monero CPU miner.
- Connects to **MoneroOcean** (`gulf.moneroocean.stream:10128`) over TLS and
  sends all rewards to your Monero wallet address.
- Monitors user activity (keyboard, mouse, X11 idle time on Linux; IOKit on
  macOS; `GetLastInputInfo` on Windows) and starts/stops mining accordingly.
- Ships with systemd (Linux) and launchd (macOS) integration so it starts
  automatically on login.

---

## Requirements

| Requirement | Minimum version |
|---|---|
| Python | 3.8+ |
| pip | any recent |

The program downloads XMRig automatically on first run – no manual steps needed.

### Optional (recommended) system packages

| Platform | Package | Purpose |
|---|---|---|
| Linux | `xprintidle` | Accurate X11 idle-time detection |
| Linux | `python3-xlib` | X11 idle fallback |

---

## Installation

```bash
# Clone the repo
git clone https://github.com/tharunchittal/mine-for-good.git
cd mine-for-good

# Run the installer (installs Python package + sets up system service)
bash install.sh

# --- OR install the Python package directly ---
pip install .
```

---

## Quick start

```bash
# 1. Enter your Monero wallet address
mine-for-good configure

# 1b. Or use a simple desktop UI for the same settings
mine-for-good configure-ui

# 2. Check what the program detected about your machine
mine-for-good specs

# 3. Start mining (foreground, Ctrl-C to stop)
mine-for-good start

# 4. Or start in the background (POSIX only)
mine-for-good start --daemon

# 5. Check whether it's running
mine-for-good status

# 6. Stop the background service
mine-for-good stop
```

---

## Configuration

Settings are stored in `~/.mine-for-good/config.json`.
Run `mine-for-good configure` for interactive setup, or edit the file directly:

```json
{
  "wallet_address": "<your Monero address>",
  "worker_name": "my-laptop",
  "pool": {
    "url": "gulf.moneroocean.stream",
    "port": 10128,
    "tls": true
  },
  "activity": {
    "idle_threshold": 60,
    "poll_interval": 5
  },
  "mining": {
    "threads": 0,
    "cpu_limit": 75
  },
  "logging": {
    "level": "INFO",
    "file": "~/.mine-for-good/mine-for-good.log"
  }
}
```

| Key | Default | Description |
|---|---|---|
| `wallet_address` | *(required)* | Your Monero wallet address |
| `worker_name` | hostname | Label shown on the pool dashboard |
| `pool.url` | `gulf.moneroocean.stream` | Mining pool hostname |
| `pool.port` | `10128` | Pool port |
| `pool.tls` | `true` | Enable TLS (recommended) |
| `activity.idle_threshold` | `60` | Seconds of inactivity before mining starts |
| `activity.poll_interval` | `5` | How often (seconds) to check for activity |
| `mining.threads` | `0` *(auto)* | Number of CPU threads (0 = physical cores − 1) |
| `mining.cpu_limit` | `75` | Per-thread CPU usage cap (%) |

---

## How it works

```
┌─────────────────────────────────────────────────────────┐
│                    mine-for-good                        │
│                                                         │
│  ┌──────────────┐   idle?    ┌──────────────────────┐  │
│  │  Activity    │──────────▶│   MinerProcess        │  │
│  │  Monitor     │  active?  │   (XMRig wrapper)     │  │
│  │  (polls      │◀──────────│                       │  │
│  │   idle time) │           │   stratum+tcps://     │  │
│  └──────────────┘           │   gulf.moneroocean.   │  │
│                             │   stream:10128        │  │
│                             └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

1. **Startup** – the service reads your config, downloads XMRig if needed, and
   auto-selects a thread count (physical cores − 1, never exceeding logical
   cores).
2. **Idle detection** – an `ActivityMonitor` thread polls the system idle timer
   every `poll_interval` seconds.  When idle time exceeds `idle_threshold`, it
   calls `MinerProcess.start()`.
3. **Active detection** – as soon as idle time drops below the threshold (a
   keystroke, mouse move, media start, etc.) `MinerProcess.stop()` is called and
   XMRig exits within seconds.
4. **Rewards** – XMRig communicates with MoneroOcean over an encrypted Stratum
   connection; mined blocks are credited directly to your wallet address.

---

## Running as a system service

### Linux (systemd user service)

`install.sh` writes `~/.config/systemd/user/mine-for-good.service`
automatically.

```bash
# Enable on login and start immediately
systemctl --user enable --now mine-for-good

# Check logs
journalctl --user -u mine-for-good -f
```

### macOS (launchd)

`install.sh` writes `~/Library/LaunchAgents/com.mine-for-good.plist`.

```bash
launchctl load ~/Library/LaunchAgents/com.mine-for-good.plist
```

---

## Development

```bash
# Install in editable mode with test dependencies
pip install -e .
pip install pytest

# Run the test suite
pytest
```

---

## License

MIT
