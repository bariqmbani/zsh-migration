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
python3 toolkit/tests/test_platform.py
python3 toolkit/tests/test_mise.py /absolute/path/to/generated-package
```

Tests require Python >=3.12. Review generated inventory/exclusions, replace `migration/` with the new package contents, and copy the matching ZIP/sidecar to `archives/`. Run Python itself through mise on a migrated development machine. Arbitrary dynamic shell programs need manual adaptation; this is a portable implementation of the captured source profile.

Paste this single prompt into your agent on the Mac or another target:

> Clone the private repository bariqmbani/zsh-migration using gh. Read AGENTS.md, README.md and migration/TARGET-AGENT-HANDOFF.md, README.md, MANUAL-INSTALL.md and VALIDATION.md. Inspect the target, verify checksums, dry-run and restore with backups. Follow tool-policy.json: category 1 tools are installed manually at latest stable outside mise (including rtk and Mike Farah yq), category 2 tools are excluded, category 3 pins remain unchanged, and uv/ruff/ty use latest through mise. Replace legacy runtime activation and preserve the eza ls/l and batcat cat aliases. You are authorized to install prerequisites, the selected mise tools and manual tools, and replace managed configuration after backups. Preserve credentials/history and legacy installations for rollback. On my M1 Pro Mac use native ARM64 and detect the actual macOS version. Complete verification without AI-provider requests; report tool versions, unresolved items, backup location and the exact rollback command.
