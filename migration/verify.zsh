#!/usr/bin/env zsh
emulate -LR zsh
setopt err_exit pipe_fail
kit=${0:A:h}
source "$kit/lib/platform.zsh"
migration_detect_platform
migration_checksum "$kit"
print -r -- "Verifying $MIGRATION_PLATFORM / $MIGRATION_ARCH"
export MIGRATION_VERIFY_KIT="$kit"
zsh_bin=$(command -v zsh)
for mode in -ic -lic; do
  "$zsh_bin" "$mode" '
    failures=0
    for tool in git curl perl mise go python node java uv pnpm mvn; do
      if command -v "$tool" >/dev/null; then print "PASS command: $tool"
      else print "FAIL command: $tool"; (( failures++ )); fi
    done
    if command -v mise >/dev/null; then
      for tool in go python node java uv pnpm mvn; do
        mise which "$tool" >/dev/null || { print "FAIL mise ownership: $tool"; (( failures++ )); }
      done
      missing=$(mise ls --missing) || { print "FAIL mise listing"; (( failures++ )); }
      [[ -z $missing ]] || { print "FAIL missing mise tools: $missing"; (( failures++ )); }
    fi
    # Manual tools require executable presence, not mise ownership.
    while IFS= read -r spec; do
      candidates=("${(@s:|:)spec}")
      found=""
      for candidate in "${candidates[@]}"; do
        if (( $+commands[$candidate] )); then found=$commands[$candidate]; break; fi
      done
      if [[ -n $found ]]; then print "PASS manual command: $spec ($found)"
      else print "PENDING manual installation: $spec (MANUAL-INSTALL.md)"; (( failures++ )); fi
    done < "$MIGRATION_VERIFY_KIT/manual-commands.txt"
    [[ ${aliases[ls]:-} == eza* && ${aliases[l]:-} == eza* && ${aliases[cat]:-} == batcat* ]] || {
      print "FAIL eza/batcat aliases"; (( failures++ ))
    }
    for fn in _zsh_autosuggest_start _zsh_highlight history-substring-search-up zinit z; do
      if (( $+functions[$fn] )); then print "PASS function: $fn"
      else print "FAIL function: $fn"; (( failures++ )); fi
    done
    [[ -n $ZSH_THEME ]] || (( failures++ ))
    [[ ${_comps[git]:-} == _git ]] || (( failures++ ))
    for annex in as-monitor bin-gem-node patch-dl rust; do
      name="zdharma-continuum/zinit-annex-$annex"
      if (( ${ZINIT_REGISTERED_PLUGINS[(Ie)$name]} )); then print "PASS annex: $annex"
      else print "FAIL annex: $annex"; (( failures++ )); fi
    done
    for link in "$HOME/.local/share/zinit/completions/_zinit" "$HOME/.local/share/zinit/plugins/_local---zinit/_zinit"; do
      [[ -e $link ]] || { print "FAIL link: $link"; (( failures++ )); }
    done
    if [[ -o zle && -t 0 ]]; then
      (( $+widgets[fzf-history-widget] )) || { print "FAIL fzf widget"; (( failures++ )); }
    else
      print "PENDING fzf widgets: verify from an interactive terminal session."
    fi
    if (( $+functions[_zsh_ai_init_widget] )); then
      print "PASS AI plugin loaded; no network request made."
    else
      print "PENDING AI: supply a local key if wanted."
    fi
    exit $(( failures > 0 ))
  '
done
print 'Automated checks passed. Complete manual checks in TARGET-AGENT-HANDOFF.md.'
