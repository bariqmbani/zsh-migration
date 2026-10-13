# Zsh and development environment migration

Migrate this WSL shell profile to **macOS, Linux, or WSL**, with **mise managing all development runtimes and tools**. Includes a sanitized source backup, portable plugins/configuration, ZIP, restore/rollback scripts, and an agent handoff. BSD configuration-only restore is experimental.

```sh
gh repo clone bariqmbani/zsh-migration
cd zsh-migration/migration
bash bootstrap.sh --dry-run
bash bootstrap.sh
zsh -f verify.zsh
```

Read [the target handoff](migration/TARGET-AGENT-HANDOFF.md) first. Default restore installs Go, Python, Node.js, Java, uv, pnpm, Maven, eza, bat, and the captured development CLIs through mise, then activates the backed-up shell configuration. `--skip-deps` explicitly selects configuration-only restore. Use a normal user account.

- `ls`/`l` use eza; `cat` uses batcat (portable wrapper for bat). Includes `ll`, `la`, `lt`, `catn` and `catp`.
- [Complete instructions and platform support](migration/README.md)
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

> Clone the private repository bariqmbani/zsh-migration using gh. Read AGENTS.md, README.md, migration/TARGET-AGENT-HANDOFF.md, migration/README.md and migration/VALIDATION.md. Inspect this machine, verify checksums, dry-run, then restore the shell and development environment with backups. Use mise for ALL development runtimes/tools/environments, including Go, Python, Node.js, Java, uv, pnpm, Maven, eza and bat; enable the eza ls/l and batcat cat aliases; replace legacy manager activation. You are authorized to install prerequisites and mise tools and replace managed configuration after backing it up. Preserve credentials/history and legacy installations for rollback. On my M1 Pro Mac use native ARM64, detect the actual macOS version, and do not assume a marketing name. Complete verification without contacting AI providers, handle deferred tools through mise where authentication/platform support allows, and report actual results, remaining blockers, backup location and exact rollback command.
