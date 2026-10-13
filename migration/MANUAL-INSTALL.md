# Manual installation: latest stable versions

These 19 tools are intentionally outside mise. Restore does not install them. Install them manually on the target using the latest stable upstream release, then open a new terminal and run verify.zsh. The source version recorded in manual-tools.json is historical evidence, not an installation pin.

| Tool | Command | macOS installation | Upstream |
| --- | --- | --- | --- |
| bat | bat, batcat | brew install bat | [Official source](https://github.com/sharkdp/bat) |
| claude-code | claude | Official native installer; select latest stable | [Official source](https://github.com/anthropics/claude-code) |
| docker-cli | docker | brew install docker (CLI only; plan an engine separately) | [Official source](https://docs.docker.com/engine/install/) |
| eza | eza | brew install eza | [Official source](https://github.com/eza-community/eza) |
| fzf | fzf | brew install fzf | [Official source](https://github.com/junegunn/fzf) |
| gh | gh | brew install gh | [Official source](https://cli.github.com/) |
| glow | glow | brew install glow | [Official source](https://github.com/charmbracelet/glow) |
| go:github.com/bojand/ghz/cmd/ghz | ghz | Go install module@latest into ~/.local/bin | [Official source](https://github.com/bojand/ghz) |
| go:golang.org/x/tools/cmd/goimports | goimports | Go install module@latest into ~/.local/bin | [Official source](https://pkg.go.dev/golang.org/x/tools/cmd/goimports) |
| go:golang.org/x/tools/gopls | gopls | Go install module@latest into ~/.local/bin | [Official source](https://go.dev/gopls/) |
| helm | helm | brew install helm | [Official source](https://helm.sh/docs/intro/install/) |
| jq | jq | brew install jq | [Official source](https://jqlang.org/download/) |
| kubectl | kubectl | brew install kubernetes-cli | [Official source](https://kubernetes.io/docs/tasks/tools/) |
| npm:@openai/codex | codex | Official standalone installer or brew install --cask codex | [Official source](https://github.com/openai/codex) |
| pypi:graphifyy | graphify | Manual uv tool install/upgrade graphifyy using mise-managed Python | [Official source](https://pypi.org/project/graphifyy/) |
| ripgrep | rg | brew install ripgrep | [Official source](https://github.com/BurntSushi/ripgrep) |
| rtk | rtk | brew install rtk | [Official source](https://github.com/rtk-ai/rtk) |
| zoxide | zoxide | brew install zoxide | [Official source](https://github.com/ajeetdsouza/zoxide) |
| yq | yq | brew install yq (Mike Farah yq) | [Official source](https://github.com/mikefarah/yq) |

## macOS

Use native Homebrew in the M1 Pro terminal. `brew update` refreshes package definitions; install missing formulas and upgrade existing ones to their current stable releases. Check the installed version against the upstream link in the table. If Homebrew lags upstream, use the vendor's current native release instead. The migration scripts do not run these manual commands.

```sh
brew update
brew install bat docker eza fzf gh glow helm jq kubernetes-cli ripgrep rtk yq zoxide
# For already-installed formulas, run brew upgrade with the relevant names.
```

`docker` supplies the CLI; a Docker engine/context needs separate configuration. Use **Mike Farah yq**, not the unrelated Python program also named yq. bat's executable on macOS is `bat`; the shell defines a `batcat` wrapper for the requested aliases.

Install Claude Code with its official native installer, selecting the latest release, or its Homebrew cask. Install Codex with its official standalone installer or Homebrew cask. Follow the upstream documentation linked in the table; no source credentials are needed to install the binaries. Do not invoke an AI request just to verify installation.

```sh
brew install --cask claude-code codex
# Upgrade an existing cask if needed. Native vendor installers are alternatives.
```

## Linux / WSL

Use the upstream instructions in the table and select the latest stable release for the detected architecture. Native package repositories are acceptable when they provide that version; distribution packages can lag upstream. Extract official release binaries into ~/.local/bin when appropriate. Do not copy the source's Linux executables to a different OS/architecture. Use the native Claude/Codex installers or release binaries; the tools are not registered with mise.

## Manual Go and Python tools (all targets)

After restore installs mise-managed Go, build these manual Go CLIs at `@latest`. Their binaries live directly in ~/.local/bin, outside mise's tool registry:

```sh
mkdir -p "$HOME/.local/bin"
GOBIN="$HOME/.local/bin" mise exec -- go install github.com/bojand/ghz/cmd/ghz@latest
GOBIN="$HOME/.local/bin" mise exec -- go install golang.org/x/tools/cmd/goimports@latest
GOBIN="$HOME/.local/bin" mise exec -- go install golang.org/x/tools/gopls@latest
```

If current upstream requires a newer Go runtime than the preserved pin, report that requirement and reconcile it explicitly before changing the user's runtime selection.

Install graphifyy directly with the selected mise-managed uv/Python; do not add it to mise.toml. For a new installation:

```sh
UV_TOOL_BIN_DIR="$HOME/.local/bin" mise exec -- uv tool install --python "$(mise which python)" graphifyy
```

For an existing installation, use `uv tool upgrade graphifyy` with the same UV_TOOL_BIN_DIR and mise execution context. Verify the installed distribution version. `graphify` is its CLI name. This isolated Python application environment is package installation, not another runtime version manager.

## Finish and verify

Open a fresh terminal after installation so commands, fzf/zoxide integration and eza/bat aliases are detected. Run `zsh -f verify.zsh` from the package directory. It checks manual executable presence and selected mise tools separately; presence alone does not establish freshness. Record installed manual versions against their latest stable upstream releases. yq's `--version` output must identify Mike Farah yq.

On a target that used an earlier migration package, back up existing mise configuration, remove manual/excluded entries from other global/project configurations too, and check command resolution. Older installed mise binaries/shims may remain for rollback; ensure manual commands resolve to their new native installations. Do not delete tools already installed on a target without reviewing them. Removed migration tools are neither installed nor required by this package.

