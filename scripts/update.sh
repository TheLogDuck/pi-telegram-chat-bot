#!/bin/bash
# Immutable entrypoint for pull-based updates and deployment.
# Dynamically resolves project root to support both dev/test and prod directories.

set -euo pipefail

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

# Resolve project root dynamically (one level up from scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"
log_info "Working directory: $PROJECT_ROOT"

log_info "Fetching and pulling latest commits from origin/main..."
git pull origin main

# Delegate execution to the application deployment script
log_info "Handing off execution to scripts/deploy.sh..."
exec bash "$SCRIPT_DIR/deploy.sh" "$@"
