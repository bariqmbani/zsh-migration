# Loaded by .zshrc after source aliases and mise activation.
# Native commands remain available with `command ls` and `command cat`.
if (( $+commands[eza] )); then
  alias ls='eza --group-directories-first'
  alias l='eza --long --all --header --git --group-directories-first'
  alias ll='eza --long --header --git --group-directories-first'
  alias la='eza --all --group-directories-first'
  alias lt='eza --tree --level=2 --group-directories-first'
fi

# mise provides `bat`; Debian also uses the executable name `batcat`.
# Prefer the mise-managed bat when both commands exist.
if (( $+commands[bat] )); then
  function batcat { command bat "$@"; }
fi
if (( $+commands[bat] || $+commands[batcat] )); then
  alias cat='batcat --paging=never --style=plain'
  alias catn='batcat --paging=never --style=numbers'
  alias catp='batcat --paging=auto'
fi
