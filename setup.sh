#!/usr/bin/env bash
set -euo pipefail

# ESP32 MicroPython Dev Station — Setup Script
# Installs everything needed on a fresh Raspberry Pi (or any Linux host).
# Safe to re-run: each step checks before acting.
#
# Usage: bash setup.sh
#        curl -fsSL https://raw.githubusercontent.com/bakedpanda/esp32-station/main/setup.sh | bash

REPO_URL="https://github.com/bakedpanda/esp32-station.git"
INSTALL_DIR="$HOME/esp32-station"
SERVICE_NAME="esp32-station"
CREDS_PATH="/etc/esp32-station/wifi.json"

log()  { echo "[setup] $*"; }
warn() { echo "[setup] WARNING: $*" >&2; }
die()  { echo "[setup] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Step 1: Pre-flight checks
# ---------------------------------------------------------------------------
log "Checking prerequisites..."

command -v git >/dev/null 2>&1 || die "git not found. Install with: sudo apt install git"

python3 -c "import venv" 2>/dev/null || die "python3-venv not available. Install with: sudo apt install python3-venv"

log "Prerequisites OK."

# ---------------------------------------------------------------------------
# Step 2: Clone or update repo (idempotent)
# ---------------------------------------------------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
    log "Repository already cloned — pulling latest..."
    # git pull from repo directory
    ( cd "$INSTALL_DIR" && git pull )
else
    log "Cloning repository to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ---------------------------------------------------------------------------
# Step 3: Create virtualenv (idempotent) and install dependencies
# ---------------------------------------------------------------------------
VENV="$INSTALL_DIR/venv"
if [ ! -f "$VENV/bin/python3" ]; then
    log "Creating virtualenv at $INSTALL_DIR/venv/bin/python3..."
    python3 -m venv "$VENV"
else
    log "Virtualenv already exists — skipping creation."
fi
log "Installing Python dependencies..."
# Use venv/bin/pip to avoid global pip pollution
"$VENV/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ---------------------------------------------------------------------------
# Step 4: Add user to dialout group (idempotent)
# Note: wrap in 'if' to prevent set -e from exiting on grep's non-zero return
# ---------------------------------------------------------------------------
if groups "$USER" | grep -q '\bdialout\b'; then
    log "User $USER already in dialout group."
else
    log "Adding $USER to dialout group (requires sudo)..."
    sudo usermod -aG dialout "$USER"
    warn "You must log out and back in (or reboot) for dialout group membership to take effect."
fi

# ---------------------------------------------------------------------------
# Step 5: Prompt for WiFi credentials (idempotent — check if file exists first)
# ---------------------------------------------------------------------------
SKIP_CREDS=0
if [ -f "$CREDS_PATH" ]; then
    log "Credentials file already exists at $CREDS_PATH."
    read -rp "Overwrite existing credentials? [y/N]: " OVERWRITE </dev/tty
    [[ "$OVERWRITE" =~ ^[Yy]$ ]] || SKIP_CREDS=1
fi

if [ "$SKIP_CREDS" -eq 0 ]; then
    echo ""
    echo "Enter WiFi credentials (will be written to $CREDS_PATH)."
    read -rp  "WiFi SSID: " WIFI_SSID </dev/tty
    read -rsp "WiFi password: " WIFI_PASSWORD </dev/tty
    echo
    # Generate a random WebREPL password — user can look it up in /etc/esp32-station/wifi.json if needed
    WEBREPL_PASSWORD=$("$VENV/bin/python3" -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12)))")
    log "WebREPL password generated automatically."
fi

# ---------------------------------------------------------------------------
# Step 6: Write credentials file (safe for special characters via Python json.dumps)
# ---------------------------------------------------------------------------
if [ "$SKIP_CREDS" -eq 0 ]; then
    log "Writing credentials to $CREDS_PATH (requires sudo)..."
    sudo mkdir -p /etc/esp32-station
    "$VENV/bin/python3" -c '
import json, sys
data = {"ssid": sys.argv[1], "password": sys.argv[2], "webrepl_password": sys.argv[3]}
print(json.dumps(data))
' "$WIFI_SSID" "$WIFI_PASSWORD" "$WEBREPL_PASSWORD" | sudo tee "$CREDS_PATH" > /dev/null
    sudo chmod 600 "$CREDS_PATH"
    log "Credentials written. File permissions set to 600."
    # Clear credential variables from environment immediately
    unset WIFI_SSID WIFI_PASSWORD WEBREPL_PASSWORD
fi

# ---------------------------------------------------------------------------
# Step 7: Patch and install systemd service (critical: substitute actual user)
# The service file hardcodes User=esp32 and /home/esp32 — must patch before installing
# ---------------------------------------------------------------------------
SERVICE_SRC="$INSTALL_DIR/esp32-station.service"
SERVICE_DST="/etc/systemd/system/esp32-station.service"

log "Installing systemd service (requires sudo)..."
sed -e "s|User=esp32|User=${USER}|g" \
    -e "s|/home/esp32|${HOME}|g" \
    "$SERVICE_SRC" | sudo tee "$SERVICE_DST" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
log "Service installed, enabled, and started."

# ---------------------------------------------------------------------------
# Step 8: Verify service is running
# ---------------------------------------------------------------------------
if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    warn "Service did not start. Check logs with: journalctl -u $SERVICE_NAME -n 20"
else
    log "Service is active."
fi

# ---------------------------------------------------------------------------
# Step 9: Print endpoint URL and claude mcp add command
# ---------------------------------------------------------------------------
HOSTNAME=$(hostname)
echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo " MCP server running at:"
echo "   http://${HOSTNAME}.local:8000/mcp"
echo ""
echo " Register with Claude Code on your main machine:"
echo "   claude mcp add --transport http esp32-station http://${HOSTNAME}.local:8000/mcp"
echo ""
echo " If hostname resolution fails, replace ${HOSTNAME}.local with the Pi's IP address."
echo " Find it with: hostname -I"
echo ""
echo " WebREPL password was generated automatically."
echo " To look it up: sudo cat $CREDS_PATH"
echo ""
echo " Next: restart your terminal session (for dialout group to take effect)."
echo "============================================================"
