#!/bin/bash
# Pull-based deployment script for development/test Telegram bot

set -e

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
    log_error "Aborting deployment. telegram-bot-test.service was NOT restarted."
}
trap 'on_error $LINENO "$BASH_COMMAND"' ERR

log_info "Starting development/test deployment..."

# Step 1: Navigate to the development/test bot directory
cd ~/pi-telegram-chat-bot-test

# Step 2: Fetch and merge latest code from origin main (or dev branch)
log_info "Pulling latest code from origin main..."
git pull origin main

# Step 3: Activate isolated Python virtual environment
log_info "Activating virtual environment..."
source venv/bin/activate

# Step 4: Install/update dependencies non-interactively
log_info "Verifying dependencies..."
pip install --no-input -r requirements.txt

# Step 5: Apply SQLite schema initialization / migrations
log_info "Applying SQLite database migrations..."
python -c "from core.db import init_db; init_db()"

# Step 6: Run test suite; halts script via trap if any test fails
log_info "Running unit tests with pytest..."
pytest

# Step 7: Restart the test systemd service (only reached if all tests pass)
log_info "All tests passed. Restarting telegram-bot-test.service..."
sudo systemctl restart telegram-bot-test.service

log_info "Deployment completed successfully."
