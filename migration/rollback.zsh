#!/usr/bin/env zsh
emulate -LR zsh
setopt err_exit pipe_fail
umask 077
kit=${0:A:h}
[[ $# == 1 ]] || { print -ru2 'Usage: zsh -f rollback.zsh BACKUP_DIRECTORY'; exit 2; }
source "$kit/lib/platform.zsh"
migration_detect_platform
migration_checksum "$kit"
source "$kit/lib/migration.zsh"
migration_rollback "$1"
print 'Open a new terminal. Native packages and the login shell remain unchanged.'
