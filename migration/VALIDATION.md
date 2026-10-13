# Validation

Validation host: WSL / Ubuntu 24.04, x86_64, Zsh 5.9, Python 3.13, 2026-10-13. No restore was performed in the live source HOME and no AI provider was contacted. The official mise binary 2026.10.8 was installed only under /tmp for configuration parsing; development runtimes were not downloaded.

## Automated checks

- Twelve portable tests cover transactions, repeat restore, newest-first rollback, preservation of later edits/history, symlinks, backup/activation failures, real public dry-run/configuration-only restore, archive integrity, sanitized source exclusions, login/non-login startup and terminal widgets.
- Six platform tests cover OS classification, native Windows rejection, native prerequisite command construction, unknown package managers, failure propagation and platform paths.
- Nine mise tests cover baseline/tool report consistency, source default/version/vendor conversion, development installs routed through mise, install failure leaving target config untouched, existing mise config rollback, legacy path cleanup/mise activation, nondefault config location rejection, real mise offline parsing/registry recognition and actual bat/batcat alias behavior for paths with spaces and piped input. The real binary test is optional when MISE_TEST_BINARY is absent; all nine were run on the source validation host.
- Syntax checks cover maintained Bash/Zsh scripts and Python modules.
- Source fzf/zoxide binaries are exercised in temporary homes but never packaged. Ubuntu fzf 0.44.1 fallback and newer fzf widget registration are tested. AI loading uses a fake test key without a request.
- Packaging scans for discovered credential literals/token patterns, rejects executable binaries and case-colliding paths, rewrites local links and checks ZIP/internal SHA-256 integrity.

Native installer commands and mise install calls are tested with stubs. Real mise parses exact pins offline and recognizes the registry names. Floating `latest` requests require network resolution and may be omitted from offline listing. None of these checks establish that every version can be downloaded or run on another platform.

## Reproduce

From the repository root (Python >=3.12):

```sh
python3 toolkit/tests/test_portable.py /absolute/path/to/generated-package
python3 toolkit/tests/test_platform.py
MISE_TEST_BINARY=/absolute/path/to/mise python3 toolkit/tests/test_mise.py /absolute/path/to/generated-package
```

Some widget tests skip when the source-host executables are unavailable. Use mise-managed Python on migrated development machines.

## Pending on target

Actual downloads/installation of the complete tool set, native library/compiler prerequisites, target tool-version availability, Apple ARM64 execution, Homebrew/Command Line Tools, macOS/BSD/other-distro restore and rollback, existing config-fragment/project override reconciliation, private CLI authentication, real terminal keypresses/notifications and project workflows. The Mac was not accessible. Follow TARGET-AGENT-HANDOFF.md and record PASS/FAIL/PENDING separately from the checksummed package.

Some custom/proprietary local commands and private Go modules are deliberately deferred with reasons in development-tools.json; select a mise backend and supply target authentication where needed. The package does not silently substitute a different tool version or reinstall competing managers.
