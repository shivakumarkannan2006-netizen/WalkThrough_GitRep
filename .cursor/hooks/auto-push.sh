#!/usr/bin/env bash
# Backup: commit and push uncommitted changes when an agent session stops.
set -euo pipefail

ROOT="$(git -C "${CURSOR_PROJECT_DIR:-.}" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

LOG_FILE="$ROOT/.cursor/hooks/auto-push.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*" >>"$LOG_FILE"
}

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  log "skip: not a git repo"
  exit 0
fi

if [[ -z "$(git status --porcelain)" ]]; then
  log "skip: working tree clean"
  exit 0
fi

log "committing uncommitted changes"
git add -A
git reset -q -- .env backend/.env backend/.venv .cursor/hooks/auto-push.log 2>/dev/null || true

if [[ -z "$(git diff --cached --name-only)" ]]; then
  log "skip: nothing staged after exclusions"
  exit 0
fi

git commit -m "chore: auto-sync from Cursor" || {
  log "commit failed"
  exit 0
}

if git push origin main >>"$LOG_FILE" 2>&1; then
  log "push succeeded"
else
  log "push failed (check auth: gh auth login --web)"
fi

exit 0
