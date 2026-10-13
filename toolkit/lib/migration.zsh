# Shared filesystem operations. No macOS dependencies, so WSL can test them.
migration_die() { print -ru2 -- "ERROR: $*"; return 1; }

migration_rel_safe() {
  [[ -n $1 && $1 != /* && $1 != *$'\n'* && $1 != *$'\t'* && "/$1/" != */../* && "/$1/" != */./* ]]
}

migration_parent_safe() {
  local rel=$1 part current=$HOME
  local -a parents
  parents=("${(@s:/:)rel:h}")
  for part in "${parents[@]}"; do
    [[ $part == . ]] && continue
    current="$current/$part"
    [[ ! -L $current ]] || { migration_die "Symlink parent requires manual review: $current"; return 1; }
    [[ ! -e $current || -d $current ]] || { migration_die "Not a directory: $current"; return 1; }
  done
}

migration_preflight() {
  local tree=$1 manifest=$2 rel
  [[ -d $HOME && -w $HOME ]] || { migration_die 'HOME must be writable'; return 1; }
  while IFS= read -r rel; do
    migration_rel_safe "$rel" || { migration_die 'Invalid managed path'; return 1; }
    migration_parent_safe "$rel" || return 1
    [[ -e "$tree/$rel" || -L "$tree/$rel" ]] || { migration_die "Missing payload: $rel"; return 1; }
  done < "$manifest"
  migration_parent_safe '.zsh-migration-backups/probe' || return 1
}

migration_apply() {
  local tree=$1 manifest=$2 rel
  migration_preflight "$tree" "$manifest" || return 1
  command mkdir -p "$HOME/.zsh-migration-backups" || return 1
  command chmod 700 "$HOME/.zsh-migration-backups" || return 1
  MIGRATION_BACKUP=$(command mktemp -d "$HOME/.zsh-migration-backups/$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX") || return 1
  print -r -- "$HOME" > "$MIGRATION_BACKUP/home"
  print -r -- preparing > "$MIGRATION_BACKUP/state"
  command cp "$manifest" "$MIGRATION_BACKUP/managed-paths.txt" || return 1
  : > "$MIGRATION_BACKUP/present.txt"
  : > "$MIGRATION_BACKUP/journal.txt"
  command mkdir -p "$MIGRATION_BACKUP/originals" "$MIGRATION_BACKUP/prepared" "$MIGRATION_BACKUP/displaced" || return 1
  # Finish ALL backup copies and replacement copies before activation starts.
  while IFS= read -r rel; do
    command mkdir -p "$MIGRATION_BACKUP/originals/${rel:h}" "$MIGRATION_BACKUP/prepared/${rel:h}" || return 1
    if [[ -e "$HOME/$rel" || -L "$HOME/$rel" ]]; then
      command cp -pPR "$HOME/$rel" "$MIGRATION_BACKUP/originals/$rel" || return 1
      print -r -- "$rel" >> "$MIGRATION_BACKUP/present.txt"
    fi
    command cp -pPR "$tree/$rel" "$MIGRATION_BACKUP/prepared/$rel" || return 1
  done < "$manifest"
  print -r -- applying > "$MIGRATION_BACKUP/state"
  while IFS= read -r rel; do
    command mkdir -p "$HOME/${rel:h}" "$MIGRATION_BACKUP/displaced/${rel:h}" || return 1
    print -r -- "$rel" >> "$MIGRATION_BACKUP/journal.txt"
    if [[ -e "$HOME/$rel" || -L "$HOME/$rel" ]]; then
      command mv "$HOME/$rel" "$MIGRATION_BACKUP/displaced/$rel" || return 1
    fi
    command mv "$MIGRATION_BACKUP/prepared/$rel" "$HOME/$rel" || return 1
  done < "$manifest"
  print -r -- installed > "$MIGRATION_BACKUP/state"
  print -r -- "Backup: $MIGRATION_BACKUP"
}

migration_rollback() {
  local backup=${1:A} rel recovery candidate candidate_state
  [[ $backup == "$HOME/.zsh-migration-backups/"* && -f "$backup/home" && -f "$backup/state" ]] || {
    migration_die 'Not a migration backup in this HOME'; return 1
  }
  [[ $(<"$backup/home") == "$HOME" ]] || { migration_die 'Backup belongs to a different HOME'; return 1; }
  [[ $(<"$backup/state") != rolled-back ]] || { print 'Already rolled back.'; return 0; }
  # Reject rolling back an older installation while a later one is still active.
  for candidate in "$HOME"/.zsh-migration-backups/*(N/); do
    [[ $candidate == "$backup" || ! -f "$candidate/state" ]] && continue
    candidate_state=$(<"$candidate/state")
    if [[ "$candidate/home" -nt "$backup/home" && $candidate_state == (installed|applying|rolling-back) ]]; then
      migration_die "Roll back the newer installation first: $candidate"; return 1
    fi
  done
  local -a items present done_items
  items=("${(@f)$(<"$backup/journal.txt")}")
  present=("${(@f)$(<"$backup/present.txt")}")
  [[ -f "$backup/rollback-done.txt" ]] || : > "$backup/rollback-done.txt"
  done_items=("${(@f)$(<"$backup/rollback-done.txt")}")
  for rel in "${items[@]}"; do
    [[ -z $rel ]] && continue
    migration_rel_safe "$rel" && migration_parent_safe "$rel" || return 1
    if (( ${present[(Ie)$rel]} )); then
      [[ -e "$backup/originals/$rel" || -L "$backup/originals/$rel" ]] || {
        migration_die "Missing original: $rel"; return 1
      }
    fi
  done
  recovery=$(command mktemp -d "$backup/rollback-saved-XXXXXXXX") || return 1
  print -r -- rolling-back > "$backup/state"
  # Current files are moved aside, never deleted: this also preserves later edits.
  for rel in "${(Oa)items[@]}"; do
    [[ -z $rel ]] && continue
    (( ${done_items[(Ie)$rel]} )) && continue
    command mkdir -p "$recovery/${rel:h}" || return 1
    if [[ -e "$HOME/$rel" || -L "$HOME/$rel" ]]; then
      command mv "$HOME/$rel" "$recovery/$rel" || return 1
    fi
    if (( ${present[(Ie)$rel]} )); then
      command cp -pPR "$backup/originals/$rel" "$HOME/$rel" || return 1
    fi
    print -r -- "$rel" >> "$backup/rollback-done.txt"
  done
  print -r -- rolled-back > "$backup/state"
  print -r -- "Restored previous configuration. Later files preserved in: $recovery"
}
