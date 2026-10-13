#!/usr/bin/env bash
# Bootstrap only Zsh when missing, then enter the verified restore workflow.
set -euo pipefail
kit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dry_run=0
skip_deps=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    --skip-deps) skip_deps=1 ;;
    --shell-only) ;;
    -h|--help) echo 'Usage: bash bootstrap.sh [--dry-run] [--skip-deps] [--shell-only]'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
# Validate the generated package even before a missing Zsh is installed.
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$kit_dir" && sha256sum -c SHA256SUMS >/dev/null)
elif command -v shasum >/dev/null 2>&1; then
  (cd "$kit_dir" && shasum -a 256 -c SHA256SUMS >/dev/null)
else
  echo 'Install sha256sum or shasum before bootstrapping.' >&2
  exit 1
fi
if ! command -v zsh >/dev/null 2>&1; then
  if (( dry_run )); then
    echo 'Zsh is missing. Normal bootstrap installs it on supported Linux package managers.'
    echo 'No changes made; rerun the dry run after Zsh is available.'
    exit 0
  fi
  if (( skip_deps )); then echo 'Install Zsh >=5.8 manually before --skip-deps.' >&2; exit 1; fi
  [[ "$(id -u)" != 0 ]] || { echo 'Run without sudo as your normal user.' >&2; exit 1; }
  [[ "$(uname -s)" == Linux ]] || { echo 'Install Zsh >=5.8 manually on this OS.' >&2; exit 1; }
  command -v sudo >/dev/null || { echo 'sudo missing; install Zsh manually.' >&2; exit 1; }
  if command -v apt-get >/dev/null; then sudo apt-get update; sudo apt-get install -y zsh
  elif command -v dnf >/dev/null; then sudo dnf install -y zsh
  elif command -v pacman >/dev/null; then sudo pacman -S --needed zsh
  elif command -v zypper >/dev/null; then sudo zypper --non-interactive install zsh
  elif command -v apk >/dev/null; then sudo apk add zsh
  else echo 'Unknown Linux package manager; install Zsh manually.' >&2; exit 1
  fi
fi
exec zsh -f "$kit_dir/restore.zsh" "$@"
