# Adapt paths to this host. Never import an architecture-specific runtime.
typeset -U path PATH
if [[ $OSTYPE == darwin* ]]; then
  case $(uname -m) in
    arm64) _migration_brew=/opt/homebrew/bin/brew ;;
    x86_64) _migration_brew=/usr/local/bin/brew ;;
    *) _migration_brew=/nonexistent ;;
  esac
  if [[ -x $_migration_brew ]]; then
    [[ ${HOMEBREW_PREFIX:-} == ${_migration_brew:h:h} ]] || eval "$("$_migration_brew" shellenv)"
  fi
elif [[ -x /home/linuxbrew/.linuxbrew/bin/brew && ${HOMEBREW_PREFIX:-} != /home/linuxbrew/.linuxbrew ]]; then
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi
unset _migration_brew
# Discard inherited paths from competing managers, including custom manager roots.
_migration_roots=("$HOME/.pyenv" "$HOME/.nvm" "$HOME/.sdkman" "$HOME/.asdf"
  "$HOME/.rbenv" "$HOME/.nodenv" "$HOME/.jenv" "$HOME/.rvm" "$HOME/.volta"
  "$HOME/.fnm" "$HOME/.local/share/fnm" "$HOME/.local/go"
  "${PYENV_ROOT:-}" "${NVM_DIR:-}" "${SDKMAN_DIR:-}" "${ASDF_DATA_DIR:-}"
  "${RBENV_ROOT:-}" "${VOLTA_HOME:-}" "${FNM_DIR:-}")
for _migration_root in "${_migration_roots[@]}"; do
  [[ -n $_migration_root ]] || continue
  _migration_kept=()
  for _migration_entry in "${path[@]}"; do
    [[ $_migration_entry == "$_migration_root" || $_migration_entry == "$_migration_root/"* ]] || _migration_kept+=("$_migration_entry")
  done
  path=("${_migration_kept[@]}")
done
unset PYENV_ROOT PYENV_VERSION PYENV_SHELL NVM_DIR NVM_BIN NVM_INC SDKMAN_DIR SDKMAN_CANDIDATES_DIR
unset SDKMAN_CANDIDATES_API SDKMAN_PLATFORM SDKMAN_BROKER_API ASDF_DIR ASDF_DATA_DIR
unset RBENV_ROOT RBENV_VERSION RBENV_SHELL NODENV_ROOT NODENV_VERSION JENV_ROOT JENV_VERSION VOLTA_HOME FNM_DIR
unset GOROOT JAVA_HOME JDK_HOME M2_HOME MAVEN_HOME GRADLE_HOME
# Shims also support commands in login shells before interactive activation.
path=("${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims" "$HOME/.local/bin" $path)
export GOPATH="${GOPATH:-$HOME/go}"
# Existing manually installed tools remain available after mise's tools.
[[ -d "$GOPATH/bin" ]] && path+=("$GOPATH/bin")
unset _migration_roots _migration_root _migration_kept _migration_entry
if [[ -z ${ANDROID_HOME:-} ]]; then
  if [[ $OSTYPE == darwin* ]]; then export ANDROID_HOME="$HOME/Library/Android/sdk"
  else export ANDROID_HOME="$HOME/Android/Sdk"; fi
fi
export ANDROID_SDK_ROOT="$ANDROID_HOME"
for _migration_dir in \
  "$HOME/.opencode/bin" "$HOME/.mimocode/bin" \
  "$HOME/.local/sonar-scanner/bin" "$ANDROID_HOME/emulator" \
  "$ANDROID_HOME/platform-tools" "$ANDROID_HOME/cmdline-tools/latest/bin"; do
  [[ -d "$_migration_dir" ]] && path+=("$_migration_dir")
done
unset _migration_dir
export PATH
