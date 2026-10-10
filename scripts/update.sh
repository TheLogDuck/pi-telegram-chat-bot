#!/bin/bash
# Immutable entrypoint for production updates and deployment.
# Pulls latest commits from Git before delegating to scripts/deploy.sh.
# This prevents self-modification hazards when deployment logic changes.

set -euo pipefail

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

# Navigate to project root
cd ~/pi-telegram-chat-bot

log_info "Fetching and pulling latest commits from origin/main..."
git pull origin main

# Delegate execution to the application deployment script
log_info "Handing off execution to scripts/deploy.sh..."
exec bash scripts/deploy.sh "$@"
