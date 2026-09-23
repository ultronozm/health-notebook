#!/usr/bin/env bash
set -euo pipefail
kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$kit_dir/tools/site/build_site.py" --repo "${HEALTH_NOTEBOOK_DIR:-$HOME/health-notebook}" "$@"
