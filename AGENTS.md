# Migration maintenance and target policy

- The user's classifications in toolkit/tool-policy.json are authoritative. Install only its 17 mise entries through mise, preserving category 3 versions and using latest for uv, ruff and ty (category 4). New discoveries require review.
- Install the 19 category 1 tools manually at their latest stable upstream version, including yq and rtk. Follow migration/MANUAL-INSTALL.md; never put these tools back into mise. Native packages, upstream binaries/installers and direct Go/uv application installs are allowed for these exceptions.
- Category 2 tools are excluded from active migration installation and verification. Keep the exclusion policy so future source backups do not reintroduce them. Do not uninstall existing target software as a side effect of restoring configuration.
- Use mise for selected development runtimes/project environments. Do not reinstall pyenv, nvm, SDKMAN, asdf, fnm, volta or another competing runtime manager. Project dependencies stay in their lockfiles.
- Preserve ls/l aliases through manually installed eza and cat aliases through batcat, with a wrapper for upstream bat on macOS.
- Preserve target credentials/history, back up existing configuration and keep legacy installations for rollback. Read migration/TARGET-AGENT-HANDOFF.md before restoring. Do not claim Mac validation from WSL tests.
- Edit toolkit/ source and regenerate migration/ and archives/ together. Replace the obsolete current ZIP so its earlier tool selection is not presented as the active package.
- Commit identity: Bariq Mbani <bariq.m70@gmail.com>. Keep this repository private.
