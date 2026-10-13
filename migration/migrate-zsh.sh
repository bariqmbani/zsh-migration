#!/usr/bin/env bash
# Install/restore only Zsh, Oh My Zsh, plugin snapshots and shell settings.
set -euo pipefail
kit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for arg in "$@"; do
  case "$arg" in
    --dry-run) ;;
    -h|--help) echo 'Usage: bash migrate-zsh.sh [--dry-run]'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
exec bash "$kit_dir/bootstrap.sh" --shell-only "$@"
