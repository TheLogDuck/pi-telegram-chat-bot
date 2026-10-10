#!/bin/bash
# Application deployment script executed after git pull completes.
# Handles virtual environment, dependencies, database migrations, testing, and service reload.

set -euo pipefail

# Timestamped logging helper functions
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
}

# Trap unexpected errors to log line number, failed command, and exit code
on_error() {
    local exit_code=$?
    local line_no=$1
    local cmd=$2
    log_error "Deployment failed at line $line_no (command: '$cmd', exit code: $exit_code)"
    log_error "Aborting deployment. telegram-bot.service was NOT restarted."
}
trap 'on_error $LINENO "$BASH_COMMAND"' ERR

log_info "Starting application deployment..."

# Step 1: Navigate to repository root
cd ~/pi-telegram-chat-bot

# Step 2: Activate isolated Python virtual environment
log_info "Activating virtual environment..."
source venv/bin/activate

# Step 3: Install/update dependencies non-interactively
log_info "Verifying dependencies..."
pip install --no-input -r requirements.txt

# Step 4: Apply SQLite schema initialization / migrations
log_info "Applying SQLite database migrations..."
python -c "from core.database import init_db; init_db()"

# Step 5: Run test suite; halts script via trap if any test fails
log_info "Running unit tests with pytest..."
pytest

# Step 6: Restart the systemd service (only reached if all tests pass)
log_info "All tests passed. Restarting telegram-bot.service..."
sudo systemctl restart telegram-bot.service

log_info "Deployment completed successfully."
