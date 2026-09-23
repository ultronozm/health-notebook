#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/health-notebook"
claude_bin="$HOME/.local/bin/claude"
mode="${HEALTH_NOTEBOOK_PERMISSION_MODE:-auto}"
case "$mode" in
  default|acceptEdits|auto|bypassPermissions) ;;
  *) echo "Unsupported HEALTH_NOTEBOOK_PERMISSION_MODE" >&2; exit 2 ;;
esac
# A new directory has nothing to resume. Fall back to a single-capacity server.
# Never change permission mode in the fallback. Persistent errors go to systemd.
"$claude_bin" remote-control --continue --name health-notebook --permission-mode "$mode" && exit 0
exec "$claude_bin" remote-control --name health-notebook --spawn=same-dir --capacity 1 --permission-mode "$mode"
