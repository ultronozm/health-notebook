#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" == 0 ]]; then
  echo "Run as the dedicated notebook user, not root" >&2; exit 1
fi
kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$HOME/health-notebook/AGENTS.md" && -d "$HOME/health-notebook/.git" ]] || {
  echo "Initialize ~/health-notebook first" >&2; exit 1;
}
[[ -x "$HOME/.local/bin/claude" ]] || { echo "Install Claude Code first" >&2; exit 1; }
systemctl --user show-environment >/dev/null
unit="$HOME/.config/systemd/user/health-notebook.service"
launcher="$HOME/.local/bin/health-notebook-remote"
# Refuse custom/older files rather than silently overwrite a running setup.
for pair in "deploy/health-notebook.service:$unit" "scripts/health-notebook-remote.sh:$launcher"; do
  source_file="${pair%%:*}"
  target_file="${pair#*:}"
  if [[ -e "$target_file" ]] && ! cmp -s "$kit_dir/$source_file" "$target_file"; then
    echo "Existing file differs; review manually: $target_file" >&2; exit 1
  fi
done
mkdir -p "$(dirname "$unit")" "$(dirname "$launcher")"
install -m 644 "$kit_dir/deploy/health-notebook.service" "$unit"
install -m 755 "$kit_dir/scripts/health-notebook-remote.sh" "$launcher"
systemctl --user daemon-reload
echo "Installed. Complete interactive login/Remote Control setup before enabling."
echo "Then: systemctl --user enable --now health-notebook.service"
