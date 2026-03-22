#!/usr/bin/env bash
# install.sh – install mine-for-good and its dependencies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== mine-for-good installer ==="
echo

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is required but was not found." >&2
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PYTHON_VERSION"

# Install Python package
echo "Installing mine-for-good …"
pip3 install --upgrade pip --quiet
pip3 install "$SCRIPT_DIR" --quiet
echo "Python package installed."

# Create config directory
CONFIG_DIR="$HOME/.mine-for-good"
mkdir -p "$CONFIG_DIR"

# Install systemd user service (Linux only)
if [[ "$(uname -s)" == "Linux" ]] && command -v systemctl &>/dev/null; then
    SERVICE_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SERVICE_DIR"

    cat > "$SERVICE_DIR/mine-for-good.service" <<EOF
[Unit]
Description=mine-for-good – background Monero CPU miner
After=network.target

[Service]
Type=simple
ExecStart=$(command -v mine-for-good) start
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    echo "Systemd user service installed."
    echo "  Enable on login : systemctl --user enable mine-for-good"
    echo "  Start now       : systemctl --user start  mine-for-good"
fi

# Install launchd agent (macOS only)
if [[ "$(uname -s)" == "Darwin" ]]; then
    PLIST_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$PLIST_DIR"

    PLIST="$PLIST_DIR/com.mine-for-good.plist"
    EXEC_PATH=$(command -v mine-for-good)

    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mine-for-good</string>
    <key>ProgramArguments</key>
    <array>
        <string>$EXEC_PATH</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$CONFIG_DIR/mine-for-good.log</string>
    <key>StandardErrorPath</key>
    <string>$CONFIG_DIR/mine-for-good.log</string>
</dict>
</plist>
EOF

    echo "launchd agent written to $PLIST"
    echo "  Load now: launchctl load $PLIST"
fi

echo
echo "=== Installation complete ==="
echo
echo "Next steps:"
echo "  1. Set your Monero wallet address:"
echo "     mine-for-good configure"
echo "  2. Check system specs:"
echo "     mine-for-good specs"
echo "  3. Start mining:"
echo "     mine-for-good start"
echo "     # or in the background:"
echo "     mine-for-good start --daemon"
