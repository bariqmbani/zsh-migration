# Restore the shell and development environment

This package adapts a WSL Oh My Zsh/Zinit profile to macOS, Linux and WSL. The selected runtimes and tools use **mise**; user-selected CLI tools are installed manually at their latest stable versions. The source machine is never modified by the builder.

## Restore

From the extracted ZIP directory or repository `migration/` directory:

```sh
bash bootstrap.sh --dry-run
bash bootstrap.sh
# Complete MANUAL-INSTALL.md, then open a fresh terminal.
zsh -f verify.zsh
```

Run as your normal account, without sudo. The wrapper verifies SHA256SUMS before doing work and can install Zsh if absent. Restore checks the native architecture, unpacks a temporary stage and checks managed paths. It bootstraps dependencies, installs mise, installs the staged development tool configuration, and only then replaces shell/mise configuration after backing up every existing managed entry. Dependency installation failure stops before shell configuration replacement. Successfully installed packages/caches may remain after failure.

`--dry-run` makes no changes to HOME or installed packages. `--skip-deps` installs only configuration; it does not claim the development environment is ready. Missing optional shell integrations stay inactive. `verify.zsh` intentionally fails until required tools exist.

## Platform scope

| Target | Installation | Validation |
| --- | --- | --- |
| Linux / WSL | apt-get, dnf, pacman, zypper, apk or existing brew for bootstrap; mise for dev tools | WSL tests; other distributions require target validation |
| macOS ARM64 / Intel | Native Homebrew bootstrap when needed; native mise tools | Target execution pending |
| BSD | Existing Zsh plus `--skip-deps`; manually supplied mise if available | Experimental configuration only |
| Native Windows | Use WSL | Unsupported native shell |

M1 Pro must report `arm64` in a native terminal. The script rejects Rosetta. The target agent must record `sw_vers`; the user's “Golden Gate 27” label is not a compatibility check. Tool vendors may not publish every captured version for every OS/architecture. Inspect and deliberately adapt versions through mise if necessary; no automatic fallback to old managers.

Zsh >=5.8 is required. A minimal target needs Bash, tar/gzip, curl, trusted CA certificates and either sha256sum or shasum before bootstrap. Git and Perl are shell/bootstrap dependencies. Native package managers may supply those prerequisites and necessary system libraries/compiler infrastructure. On a Mac, finish Command Line Tools installation if prompted. The selected mise tools are installed automatically. Shell CLIs fzf/zoxide/jq/eza/bat and the other manual tools are installed separately using MANUAL-INSTALL.md.

## mise policy and versions

`mise-tools.toml` is the readable copy of the active payload's `~/.config/mise/config.toml`. `tool-policy.json` is authoritative; source discovery cannot override the user's classification. `development-tools.json` contains selected tool evidence and unclassified/deferred items. `manual-tools.json` and MANUAL-INSTALL.md describe manual installations.

- **Category 1:** 19 manual tools, always latest stable and outside mise, including yq. Native package managers, official release binaries/installers and direct Go/uv application installs are allowed for these specific exceptions.
- **Category 2:** 18 excluded tools. They are absent from active tool lists and installation/verification requirements. A denylist prevents rediscovery from adding them back. Restore does not uninstall software already present on the target.
- **Category 3:** preserve the exact user-approved mise selections, including the existing Maven `latest` selector.
- **Category 4:** uv, ruff and ty use `latest` through mise.

There are 17 active mise entries. These include Go, Python, Node.js, Java, Bun, Deno, pnpm, Maven, protoc and the retained Go code-generation tools. `latest` resolves at target install time; this is not a reproducibility lock. Changing a category 3 pin requires a deliberate recorded decision. Source evidence can record an older version of a manual tool; that is not an installation pin.

Read [MANUAL-INSTALL.md](MANUAL-INSTALL.md) for macOS/Linux instructions. The restore script never installs manual tools or reintroduces excluded tools. Directly built manual Go tools use mise-managed Go; graphifyy uses mise-managed uv/Python for an isolated application environment. They remain outside mise's tool registry. Node supplies npm; pnpm is managed directly by mise. For unclassified future discoveries, review and classify them before adding an installer. Private Go tools require target authentication and review; they are deferred rather than installed automatically.

Use project mise.toml for per-project runtime selection and mise-managed uv/pnpm for environments/dependencies:

```sh
# Inside a project; these examples create project configuration.
mise use python@3.13 node@24
mise exec -- uv venv
mise exec -- pnpm install
```

Docker engines, OS services, GUI applications, Apple SDKs and Android system images need separate target planning. The manual Docker entry installs its CLI; it does not establish a working engine. No credentials or private network/TLS bypass settings are activated.

The generated shell removes known inherited legacy manager paths/variables, disables their Oh My Zsh activation plugins and activates mise once. It preserves legacy installations on disk for rollback. `auto_install=false` prevents opening a shell from implicitly downloading missing tools. `.nvmrc`, `.python-version` and `.sdkmanrc` support is enabled through mise's idiomatic file settings; verify project-specific selections on the target. Existing project environments are not copied.

## Interactive aliases

The generated `.zshrc` loads these after mise activation and the source aliases:

| Alias | Behavior |
| --- | --- |
| `ls` | eza, directories first |
| `l` | eza detailed listing, hidden files, headings and Git status |
| `ll` | eza detailed listing with headings and Git status |
| `la` | eza including hidden files |
| `lt` | eza tree, two levels deep |
| `cat` | batcat syntax highlighting, no pager or decorations |
| `catn` | batcat with line numbers, no pager |
| `catp` | batcat with automatic paging |

Both **eza** and **bat** are installed manually at latest stable. A `batcat` function forwards to `bat` when that is the available executable name (including macOS); an existing Debian `batcat` works too. The upstream `bat` command is preferred when both names exist. Aliases are enabled only when the tool exists, so configuration-only restore still has working native commands. `command ls` and `command cat` bypass aliases for original behavior. Target local overrides are loaded afterward. These are interactive conveniences; eza/bat options differ from system ls/cat. See [eza options](https://github.com/eza-community/eza#command-line-options) and [bat documentation](https://github.com/sharkdp/bat).

## Configuration and backup

`managed-paths.txt` is the exact replacement list: startup files, bundled Oh My Zsh/Zinit, completions, migrated settings and `~/.config/mise/config.toml`. Existing mise global configuration is backed up and replaced; inspect it and merge wanted target settings deliberately afterward. Other mise config fragments, project configs, local shell overrides and system startup scripts may change tool precedence; review them before claiming migration success. Nondefault config-location overrides are rejected by restore to avoid installing invisible configuration.

Backups are private directories under `~/.zsh-migration-backups/`. Every existing managed entry is copied before activation starts. Repeat restores produce separate backups. Roll back newest first:

```sh
zsh -f rollback.zsh "$HOME/.zsh-migration-backups/EXACT-DIRECTORY-PRINTED-BY-RESTORE"
```

Rollback preserves later edits in `rollback-saved-*` and restores prior shell/mise config. It does not uninstall downloaded tools, mise, native packages or Homebrew, and does not remove legacy manager installations. Open a fresh terminal after restore or rollback; the current shell retains its old functions/environment. The login shell is not changed automatically.

Source history, zoxide navigation data, credentials, caches and architecture-specific binaries are excluded. `source-backup.tar.gz` holds sanitized reference files, including original manager hooks and WSL-only settings; never source those originals on the target. `payload.tar.gz` contains active portable configuration and plugin snapshots. Git metadata is excluded; plugin snapshots do not auto-update. `inventory.json` records upstream commits, modifications, exclusions and checksums.

The builder captures this known source layout and literal theme/plugin declarations. It will stop if required source files are missing or dynamic declarations cannot be translated. It does not evaluate arbitrary source shell programs. Alias/export migration uses a narrow portability allowlist; all other captured settings remain reference-only for the target agent.

Optional private values belong in `~/.zsh-migration-secrets.zsh` (chmod 600); local customizations belong in `~/.zsh-migration-local.zsh`. These files are never overwritten or packaged. AI stays disabled until a local key is configured. Do not print keys or contact AI providers while verifying. `zsh_codex` remains disabled as on the source.

## Integrity and development

```sh
# Linux / WSL
sha256sum -c SHA256SUMS
# macOS
shasum -a 256 -c SHA256SUMS
```

Verify the ZIP's matching `.sha256` in its containing directory before extraction. Internal checksums verify its contents, not publisher identity. Use the trusted private repository as the source of the archive/checksum pair.

Edit maintained `toolkit/` files in the repository and rebuild with `bash toolkit/backup.sh`. Do not edit a generated checksummed package in place. See VALIDATION.md for tests and target checks.

Official references: [mise installation](https://mise.jdx.dev/installing-mise.html), [activation](https://mise.jdx.dev/cli/activate.html), [configuration](https://mise.jdx.dev/configuration.html), [Java](https://mise.jdx.dev/lang/java.html), [npm backend](https://mise.jdx.dev/dev-tools/backends/npm.html), [pypi backend](https://mise.jdx.dev/dev-tools/backends/pypi.html), [Go backend](https://mise.jdx.dev/dev-tools/backends/go.html).
