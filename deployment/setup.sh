#!/usr/bin/env bash
# =============================================================================
# deployment/setup.sh — One-shot EC2 bootstrap for the BI Orchestrator
#
# Run once on a fresh Ubuntu 22.04 t2.micro instance:
#   bash ~/app/deployment/setup.sh
#
# Assumes project files have already been copied to ~/app/ via scp.
# Requires AWS CLI v2 and IAM role (or instance profile) with SSM read access.
# =============================================================================

set -euo pipefail

APP_DIR="$HOME/app"
SERVICE_NAME="bi-orchestrator"
PYTHON="python3"

echo "==> [1/7] Updating packages and installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv nginx git awscli

echo "==> [2/7] Creating Python virtual environment..."
cd "$APP_DIR"
$PYTHON -m venv .venv
source .venv/bin/activate

echo "==> [3/7] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> [4/7] Seeding database with 2,000 mock customer records..."
$PYTHON generate_data.py
echo "      telecom.db populated."

echo "==> [5/7] Pulling API keys from AWS SSM Parameter Store..."
ANTHROPIC_KEY=$(aws ssm get-parameter \
    --name /bi-orchestrator/ANTHROPIC_API_KEY \
    --with-decryption \
    --query Parameter.Value \
    --output text)

LANGCHAIN_KEY=$(aws ssm get-parameter \
    --name /bi-orchestrator/LANGCHAIN_API_KEY \
    --with-decryption \
    --query Parameter.Value \
    --output text)

cat > "$APP_DIR/.env" <<EOF
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=${LANGCHAIN_KEY}
LANGCHAIN_PROJECT=bi-orchestrator
SQLITE_DB_PATH=telecom.db
EOF
echo "      .env written."

echo "==> [6/7] Installing systemd service..."
# Patch the app dir path into the service file
sudo cp "$APP_DIR/deployment/bi-orchestrator.service" \
        /etc/systemd/system/${SERVICE_NAME}.service

sudo sed -i "s|/home/ubuntu/app|${APP_DIR}|g" \
        /etc/systemd/system/${SERVICE_NAME}.service

sudo systemctl daemon-reload
sudo systemctl enable  ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}
echo "      systemd service enabled and started."

echo "==> [7/7] Installing Nginx reverse-proxy config..."
sudo cp "$APP_DIR/deployment/nginx.conf" \
        /etc/nginx/sites-available/${SERVICE_NAME}
sudo ln -sf /etc/nginx/sites-available/${SERVICE_NAME} \
             /etc/nginx/sites-enabled/${SERVICE_NAME}

# Disable default Nginx site to avoid port conflicts
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl restart nginx
echo "      Nginx configured and restarted."

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "  App URL : http://$(curl -s ifconfig.me)"
echo "  Status  : sudo systemctl status ${SERVICE_NAME}"
echo "  Logs    : journalctl -u ${SERVICE_NAME} -f"
echo "============================================================"
