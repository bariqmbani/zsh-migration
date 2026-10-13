# Zsh and development environment migration

Migrate this WSL shell profile to **macOS, Linux, or WSL**, with **mise managing the selected runtimes and tools**. Includes a sanitized source backup, portable plugins/configuration, ZIP, restore/rollback scripts, and an agent handoff. BSD configuration-only restore is experimental.

```sh
gh repo clone bariqmbani/zsh-migration
cd zsh-migration/migration
bash bootstrap.sh --dry-run
bash bootstrap.sh
# Complete MANUAL-INSTALL.md, then open a fresh terminal.
zsh -f verify.zsh
```

For **Zsh only**, use:

```sh
cd zsh-migration/migration
bash migrate-zsh.sh --dry-run
bash migrate-zsh.sh
zsh -f verify.zsh
```

This installs missing Zsh on supported Linux package managers and restores the bundled Oh My Zsh/plugin snapshots and shell settings. It skips development tools, mise activation/configuration replacement, and the manual-install list. The verifier detects this scope automatically. macOS normally has Zsh already; BSD requires an existing supported Zsh. Existing fzf/zoxide/eza/bat integrations load only when available.

Read [the target handoff](migration/TARGET-AGENT-HANDOFF.md) first. Default restore installs the 17 selected mise tools, then activates the backed-up shell configuration. Install the 19 manual tools at their latest stable version using [MANUAL-INSTALL.md](migration/MANUAL-INSTALL.md), including eza, bat, rtk and yq. The 18 category 2 tools are excluded. Category 3 pins are preserved; uv, ruff and ty use `latest`. `--skip-deps` explicitly selects configuration-only restore. Use a normal user account.

- `ls`/`l` use eza; `cat` uses batcat (portable wrapper for bat). Includes `ll`, `la`, `lt`, `catn` and `catp`.
- [Complete instructions and platform support](migration/README.md)
- [Manual installation](migration/MANUAL-INSTALL.md) and [authoritative tool policy](toolkit/tool-policy.json)
- [Tool versions](migration/mise-tools.toml) and [discovery evidence/deferred tools](migration/development-tools.json)
- [Validation and limitations](migration/VALIDATION.md)
- [ZIP and SHA-256 sidecar](archives/)

`toolkit/` is the maintained source. `migration/` is the current self-contained generated package. The source snapshot preserves Oh My Zsh, Zinit, plugins, completions, theme, portable aliases and related shell files. Credentials, command/navigation history, caches, Git metadata and platform-specific executables are excluded. Existing target history and separate private/local overrides are preserved. The live WSL setup and previous Mac-specific repository are unchanged.

To refresh on a source with this Oh My Zsh/Zinit layout (Python >=3.11, Bash, Git and Zsh):

```sh
bash toolkit/backup.sh --source-home "$HOME" --output-dir "$PWD/dist"
python3 toolkit/tests/test_portable.py /absolute/path/to/generated-package
python3 toolkit/tests/test_shell_only.py /absolute/path/to/generated-package
python3 toolkit/tests/test_platform.py
python3 toolkit/tests/test_mise.py /absolute/path/to/generated-package
```

Tests require Python >=3.12. Review generated inventory/exclusions, replace `migration/` with the new package contents, and copy the matching ZIP/sidecar to `archives/`. Run Python itself through mise on a migrated development machine. Arbitrary dynamic shell programs need manual adaptation; this is a portable implementation of the captured source profile.

Paste this prompt into your agent after replacing the platform and scope placeholders:

```text
Target platform: <TARGET_PLATFORM>
Migration scope: <MIGRATION_SCOPE: zsh-only or full>

Set up the requested migration scope from the private repository
bariqmbani/zsh-migration. Clone it with gh, or use an existing checkout.

Read these files from the repository root:
AGENTS.md, README.md, toolkit/tool-policy.json,
migration/TARGET-AGENT-HANDOFF.md, migration/README.md,
migration/MANUAL-INSTALL.md, and migration/VALIDATION.md.

Inspect this machine, verify the package checksums, and run the dry run.
For zsh-only scope, run bash migration/migrate-zsh.sh --dry-run, then
bash migration/migrate-zsh.sh. This installs Zsh when needed and restores
Oh My Zsh, plugin snapshots, and shell settings. Do not install development
tools or activate mise; preserve the target runtime environment and mise config.

For full scope, run bash migration/bootstrap.sh --dry-run, then
bash migration/bootstrap.sh. Restore with backups and follow toolkit/tool-policy.json:
- Install category 1 tools manually at their latest stable versions, outside
  mise. This includes rtk. Install yq from https://github.com/mikefarah/yq.
- Exclude category 2 tools from installation.
- Keep category 3 versions unchanged in mise.
- Use latest for uv, ruff, and ty through mise.

For full scope, replace legacy runtime-manager activation with mise. Use the
eza ls/l aliases and batcat cat aliases when those tools are available
(using a wrapper for bat when needed). Install eza/bat only in full scope. You are authorized to install prerequisites and tools within
the selected scope, and replace managed configuration after backing it up.
Preserve credentials, history, and legacy installations needed for rollback.

Detect the actual OS version and architecture; use native executables.
After completing the selected installation scope, open a fresh terminal and run the
verification steps. Do not contact AI providers during verification.
Report installed versions, verification results, unresolved items, the
backup location, and the exact rollback command.
```

The selected `yq` is the YAML processor maintained by Mike Farah at
[mikefarah/yq](https://github.com/mikefarah/yq). The name identifies its author;
install the command named `yq` (on macOS: `brew install yq`).
