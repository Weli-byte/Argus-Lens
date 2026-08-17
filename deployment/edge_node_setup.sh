#!/usr/bin/env bash
# edge_node_setup.sh — Bootstrap an ArgusLens edge node on ARM/x86 Linux
# Usage: sudo bash edge_node_setup.sh [--cloud-url URL] [--node-id ID]
set -euo pipefail

CLOUD_URL=""
NODE_ID="$(hostname)"
INSTALL_DIR="/opt/arguslens"
SERVICE_FILE="/etc/systemd/system/arguslens-edge.service"
LOG_DIR="/var/log/arguslens"
DATA_DIR="/var/lib/arguslens"
PYTHON_MIN="3.10"

# -------------------------------------------------------------------------
# Argument parsing
# -------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cloud-url) CLOUD_URL="$2"; shift 2 ;;
    --node-id)   NODE_ID="$2";   shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# -------------------------------------------------------------------------
# Preflight checks
# -------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo)" >&2
  exit 1
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(printf '%s\n' "$PYTHON_MIN" "$PY_VER" | sort -V | head -n1)" != "$PYTHON_MIN" ]]; then
  echo "Python >= $PYTHON_MIN required (found $PY_VER)" >&2
  exit 1
fi

echo "[1/7] Preflight OK — Python $PY_VER, node_id=$NODE_ID"

# -------------------------------------------------------------------------
# System packages
# -------------------------------------------------------------------------
apt-get update -q
apt-get install -y -q \
  python3-venv python3-pip \
  libgomp1 \
  redis-tools \
  curl jq

echo "[2/7] System packages installed"

# -------------------------------------------------------------------------
# Directories
# -------------------------------------------------------------------------
mkdir -p "$INSTALL_DIR" "$LOG_DIR" "$DATA_DIR/models" "$DATA_DIR/cache"
chmod 750 "$LOG_DIR" "$DATA_DIR"

echo "[3/7] Directories created"

# -------------------------------------------------------------------------
# Python virtual environment + dependencies
# -------------------------------------------------------------------------
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

pip install --upgrade pip --quiet
pip install \
  fastapi uvicorn[standard] \
  redis aiohttp \
  psutil \
  torch torchvision --index-url https://download.pytorch.org/whl/cpu \
  onnxruntime \
  numpy \
  --quiet

echo "[4/7] Python environment ready"

# -------------------------------------------------------------------------
# ArgusLens application
# -------------------------------------------------------------------------
if [[ -d "$INSTALL_DIR/app" ]]; then
  echo "[5/7] App directory exists — skipping copy (update manually)"
else
  mkdir -p "$INSTALL_DIR/app"
  echo "[5/7] App directory created — copy ArgusLens source here"
fi

# -------------------------------------------------------------------------
# Environment file
# -------------------------------------------------------------------------
ENV_FILE="$INSTALL_DIR/edge.env"
cat > "$ENV_FILE" <<EOF
EDGE_NODE=true
NODE_ID=${NODE_ID}
CLOUD_SYNC_URL=${CLOUD_URL}
INFERENCE_STRATEGY=edge_first
AUTONOMY_LEVEL=autonomous
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
DATA_DIR=${DATA_DIR}
EOF
chmod 600 "$ENV_FILE"

echo "[6/7] Environment file written to $ENV_FILE"

# -------------------------------------------------------------------------
# systemd service
# -------------------------------------------------------------------------
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=ArgusLens Edge Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/app
EnvironmentFile=${ENV_FILE}
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
RestartSec=10
StandardOutput=append:${LOG_DIR}/edge.log
StandardError=append:${LOG_DIR}/edge.err
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable arguslens-edge

echo "[7/7] systemd service installed — start with: systemctl start arguslens-edge"
echo
echo "ArgusLens edge node setup complete."
echo "  Install dir:  $INSTALL_DIR"
echo "  Logs:         $LOG_DIR"
echo "  Data:         $DATA_DIR"
echo "  Node ID:      $NODE_ID"
[[ -n "$CLOUD_URL" ]] && echo "  Cloud URL:    $CLOUD_URL"
