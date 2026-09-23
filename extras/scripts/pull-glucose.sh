#!/usr/bin/env bash
set -euo pipefail
umask 077
kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
notebook_dir="${HEALTH_NOTEBOOK_DIR:-$HOME/health-notebook}"
state_dir="$HOME/.local/state/health-notebook"
mkdir -p "$state_dir"
# Linux flock releases automatically on exit, including a killed process.
exec 9>"$state_dir/librelinkup.lock"
flock -n 9 || exit 0
exec "$kit_dir/.venv/bin/python" "$kit_dir/extras/librelinkup/fetch_glucose.py" pull \
  --env-file "$HOME/.config/health-notebook/librelinkup.env" \
  --raw-dir "$notebook_dir/data/raw/librelinkup" \
  --state-file "$state_dir/librelinkup-session.json" --quiet "$@"
