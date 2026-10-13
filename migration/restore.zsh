#!/usr/bin/env zsh
emulate -LR zsh
setopt err_exit pipe_fail
umask 077
kit=${0:A:h}
dry_run=0
skip_deps=0
for option in "$@"; do
  case $option in
    --dry-run) dry_run=1 ;;
    --skip-deps) skip_deps=1 ;;
    -h|--help) print 'Usage: zsh -f restore.zsh [--dry-run] [--skip-deps]'; exit 0 ;;
    *) print -ru2 -- "Unknown option: $option"; exit 2 ;;
  esac
done
(( EUID != 0 || dry_run )) || { print -ru2 'Run as your normal account, without sudo.'; exit 1; }
[[ -z ${ZDOTDIR:-} || ${ZDOTDIR:A} == ${HOME:A} ]] || {
  print -ru2 'Custom ZDOTDIR detected. Review it with the target agent before installation.'; exit 1
}
unset ZDOTDIR
# Managed paths use conventional locations; reject overrides that would hide them.
for variable in XDG_CONFIG_HOME MISE_CONFIG_DIR MISE_GLOBAL_CONFIG_FILE MISE_CONFIG_FILE; do
  value=${(P)variable}
  [[ -z $value ]] || { print -ru2 "Unset $variable or adapt managed paths before restoring."; exit 1; }
done
source "$kit/lib/platform.zsh"
migration_detect_platform
migration_checksum "$kit"
source "$kit/lib/migration.zsh"
autoload -Uz is-at-least
is-at-least 5.8 || { print -ru2 'Zsh 5.8 or newer is required.'; exit 1; }
print -r -- "Target: $MIGRATION_PLATFORM / $MIGRATION_ARCH / $HOME"
stage=$(mktemp -d "${TMPDIR:-/tmp}/zsh-migration.XXXXXXXX")
trap 'command rm -rf -- "$stage"' EXIT
tar -xzf "$kit/payload.tar.gz" -C "$stage"
migration_preflight "$stage" "$kit/managed-paths.txt"
migration_package_manager
migration_missing_dependencies
print -r -- "Package manager: $MIGRATION_MANAGER"
print -r -- "Missing dependencies: ${MIGRATION_MISSING[*]:-none}"
print 'Mise tools: mise-tools.toml (installed by default)'
print 'Manual tools: MANUAL-INSTALL.md (install latest stable on target; includes yq)'
print 'Managed destinations (existing entries will be backed up):'
cat "$kit/managed-paths.txt"
if (( dry_run )); then
  print 'Dry run complete. No home configuration or packages changed.'
  exit 0
fi
if (( ! skip_deps )); then
  migration_install_dependencies "$stage"
else
  print 'Dependency installation skipped; unavailable optional integrations remain inactive.'
fi
if ! migration_apply "$stage" "$kit/managed-paths.txt"; then
  print -ru2 -- "Installation interrupted. Backup: ${MIGRATION_BACKUP:-not created}"
  [[ -z ${MIGRATION_BACKUP:-} ]] || print -ru2 -- "Recover: zsh -f ${(q)kit}/rollback.zsh ${(q)MIGRATION_BACKUP}"
  exit 1
fi
print 'Configuration installed. Complete MANUAL-INSTALL.md, open a NEW terminal, then run zsh -f verify.zsh.'
print 'AI needs a local key in ~/.zsh-migration-secrets.zsh. Existing target history is preserved.'
print 'The login shell is unchanged; use zsh interactively or configure it separately.'
