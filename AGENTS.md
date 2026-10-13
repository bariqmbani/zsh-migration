# Migration maintenance and target policy

- Use **mise for every development runtime, tool and environment**: Go, Python, Node.js, Java, uv, pnpm, Maven, eza, bat, and additional tools. Use registry entries or mise npm/pypi/go/cargo backends. Do not reinstall pyenv, nvm, SDKMAN, asdf, fnm, volta, or another competing manager.
- Preserve the requested interactive aliases: ls/l through eza and cat through batcat, with a batcat wrapper for mise-managed bat on macOS.
- For project environments, use project mise.toml and mise-managed uv/pnpm/etc. Package dependencies remain in project lockfiles; do not turn every library into a global tool.
- Native packages are limited to bootstrapping Zsh/mise (Git, curl, certificates, archive/checksum utilities) and unavoidable system libraries/compiler infrastructure. Never silently fall back to brew/apt/npm -g/uv tool install for development tools that should be mise-managed. Report unsupported tools and find an appropriate mise backend.
- Preserve target credentials/history and back up existing configuration. Do not delete legacy manager installations; rollback may need them.
- Read migration/TARGET-AGENT-HANDOFF.md before restoring. Do not claim Mac validation from WSL tests.
- Edit toolkit/ source; regenerate migration/ and archives/ together. Never hand-edit checksummed files without rebuilding their checksums/package.
- Commit identity: Bariq Mbani <bariq.m70@gmail.com>. Keep this repository private.
