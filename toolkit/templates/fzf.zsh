# Use integration matching the target binary, including older distro packages.
if (( $+commands[fzf] )) && [[ -o interactive && -o zle && -t 0 ]]; then
  if _migration_fzf_init=$(fzf --zsh 2>/dev/null); then
    eval "$_migration_fzf_init"
  else
    for _migration_fzf_dir in \
      /usr/share/doc/fzf/examples /usr/share/fzf/shell /usr/share/fzf \
      /usr/local/share/fzf/shell /usr/local/share/fzf \
      "${HOMEBREW_PREFIX:-/nonexistent}/opt/fzf/shell"; do
      if [[ -r "$_migration_fzf_dir/key-bindings.zsh" && -r "$_migration_fzf_dir/completion.zsh" ]]; then
        source "$_migration_fzf_dir/completion.zsh"
        source "$_migration_fzf_dir/key-bindings.zsh"
        break
      fi
    done
  fi
  unset _migration_fzf_init _migration_fzf_dir
fi
