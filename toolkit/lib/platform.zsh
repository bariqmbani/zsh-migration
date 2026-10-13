# Platform detection and native dependencies. No installation on source/build.
migration_classify_platform() {
  case $1 in
    Darwin) MIGRATION_PLATFORM=macos ;;
    Linux)
      MIGRATION_PLATFORM=linux
      [[ ${(L)2} == *microsoft* || ${(L)2} == *wsl* || -n $3 ]] && MIGRATION_PLATFORM=wsl
      ;;
    FreeBSD|OpenBSD|NetBSD|DragonFly) MIGRATION_PLATFORM=${(L)1} ;;
    *) print -ru2 -- "Unsupported kernel: $1. Native Windows requires WSL."; return 1 ;;
  esac
  return 0
}

migration_detect_platform() {
  migration_classify_platform "$(uname -s)" "$(uname -r)" "${WSL_DISTRO_NAME:-}" || return 1
  MIGRATION_ARCH=$(uname -m)
  if [[ $MIGRATION_PLATFORM == macos ]] && [[ $(sysctl -in sysctl.proc_translated 2>/dev/null) == 1 ]]; then
    print -ru2 'Use a native Mac terminal instead of Rosetta for dependency installation.'
    return 1
  fi
}

migration_checksum() {
  if (( $+commands[sha256sum] )); then
    (cd "$1" && sha256sum -c SHA256SUMS >/dev/null)
  elif (( $+commands[shasum] )); then
    (cd "$1" && shasum -a 256 -c SHA256SUMS >/dev/null)
  else
    print -ru2 'Install sha256sum (coreutils) or shasum (Perl) to verify the package.'
    return 1
  fi
}

migration_package_manager() {
  MIGRATION_MANAGER=manual
  local name
  if [[ $MIGRATION_PLATFORM == macos ]]; then MIGRATION_MANAGER=brew; return 0; fi
  if [[ $MIGRATION_PLATFORM == (linux|wsl) ]]; then
    for name in apt-get dnf pacman zypper apk; do
      if (( $+commands[$name] )); then MIGRATION_MANAGER=$name; return 0; fi
    done
    (( $+commands[brew] )) && MIGRATION_MANAGER=brew
  fi
  return 0
}

migration_package_command() {
  # Constructs argv without evaluating package names or command strings.
  local manager=$1
  shift
  case $manager in
    apt-get) MIGRATION_INSTALL_COMMAND=(sudo apt-get install -y "$@") ;;
    dnf) MIGRATION_INSTALL_COMMAND=(sudo dnf install -y "$@") ;;
    pacman) MIGRATION_INSTALL_COMMAND=(sudo pacman -S --needed "$@") ;;
    zypper) MIGRATION_INSTALL_COMMAND=(sudo zypper --non-interactive install "$@") ;;
    apk) MIGRATION_INSTALL_COMMAND=(sudo apk add "$@") ;;
    brew) MIGRATION_INSTALL_COMMAND=(brew install "$@") ;;
    *) print -ru2 'Install dependencies yourself and rerun with --skip-deps.'; return 1 ;;
  esac
}

migration_missing_dependencies() {
  local tool
  MIGRATION_MISSING=()
  for tool in git curl perl tar gzip; do
    (( $+commands[$tool] )) || MIGRATION_MISSING+=("$tool")
  done
}

migration_install_dependencies() {
  local staging=$1 brew_path prefix
  migration_missing_dependencies
  if [[ $MIGRATION_PLATFORM == macos && ${#MIGRATION_MISSING} -gt 0 ]]; then
    case $MIGRATION_ARCH in
      arm64) prefix=/opt/homebrew ;;
      x86_64) prefix=/usr/local ;;
      *) print -ru2 "Unsupported Mac architecture: $MIGRATION_ARCH"; return 1 ;;
    esac
    brew_path="$prefix/bin/brew"
    if [[ ! -x $brew_path ]]; then
      /usr/bin/curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$staging/homebrew-install.sh" || return 1
      /bin/bash "$staging/homebrew-install.sh" || return 1
    fi
    [[ -x $brew_path ]] || return 1
    eval "$("$brew_path" shellenv)" || return 1
  fi
  rehash
  migration_missing_dependencies
  if (( ${#MIGRATION_MISSING} )); then
  migration_package_command "$MIGRATION_MANAGER" "${MIGRATION_MISSING[@]}" || return 1
  if [[ $MIGRATION_MANAGER != brew ]]; then
    (( $+commands[sudo] )) || { print -ru2 'sudo is unavailable; install dependencies manually and use --skip-deps.'; return 1; }
  fi
  [[ $MIGRATION_MANAGER != apt-get ]] || sudo apt-get update || return 1
  "${MIGRATION_INSTALL_COMMAND[@]}" || return 1
  rehash
  migration_missing_dependencies
  (( ${#MIGRATION_MISSING} == 0 )) || { print -ru2 "Still missing: ${MIGRATION_MISSING[*]}"; return 1; }
  fi
  migration_install_mise_tools "$staging" || return 1
}


migration_install_mise_tools() {
  local staging=$1 mise_bin
  # A new binary is installed only when mise is absent. Never edit source shell files.
  if [[ -x "$HOME/.local/bin/mise" ]]; then
    mise_bin="$HOME/.local/bin/mise"
  elif (( $+commands[mise] )); then
    mise_bin=$commands[mise]
  else
    [[ $MIGRATION_PLATFORM == (macos|linux|wsl) ]] || {
      print -ru2 'Install native mise manually for this platform, or use --skip-deps.'; return 1
    }
    curl -fsSL https://mise.run -o "$staging/mise-install.sh" || return 1
    MISE_INSTALL_PATH="$HOME/.local/bin/mise" MISE_INSTALL_HELP=0 sh "$staging/mise-install.sh" || return 1
    mise_bin="$HOME/.local/bin/mise"
  fi
  [[ -x $mise_bin ]] || return 1
  print 'Installing development runtimes and CLI tools with mise (see mise-tools.toml).'
  (
    # Stay outside projects and isolate config resolution. Existing target mise config
    # is replaced by the filesystem transaction only AFTER every tool install succeeds.
    cd "$staging" || exit 1
    unset GOROOT JAVA_HOME JDK_HOME M2_HOME MAVEN_HOME GRADLE_HOME MISE_ENV MISE_CONFIG_FILE
    export MISE_GLOBAL_CONFIG_FILE="$staging/.config/mise/config.toml"
    export MISE_AUTO_INSTALL=false
    export MISE_YES=1
    # Install runtime prerequisites first so npm/go/Python backends never use old managers.
    "$mise_bin" install go python node java uv pnpm maven || exit 1
    "$mise_bin" install || exit 1
    "$mise_bin" reshim || exit 1
  ) || return 1
}
