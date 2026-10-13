#!/usr/bin/env python3
"""Read source metadata, never source dotfiles or execute installed CLI packages."""
import json
from pathlib import Path
import re
import shutil
import subprocess


def version_key(value):
    return tuple(int(x) for x in re.findall(r'\d+', value))


def select_version(root, selector, prefix=''):
    versions = sorted((p.name.removeprefix(prefix) for p in root.glob('*') if p.is_dir()), key=version_key)
    matching = [v for v in versions if v == selector or v.startswith(selector + '.')]
    return matching[-1] if matching else (versions[-1] if versions else None)


def collect(home):
    tools = {name: 'latest' for name in ('go', 'python', 'node', 'java', 'uv', 'pnpm', 'maven',
                                         'fzf', 'zoxide', 'jq', 'eza', 'bat')}
    evidence = {name: 'Requested baseline; latest where source has no resolved version' for name in tools}
    deferred = []

    def add(name, version, reason):
        if version and re.fullmatch(r'[A-Za-z0-9_.+/-]+', version):
            tools[name] = version
            evidence[name] = reason

    def read(rel):
        p = home / rel
        return p.read_text().strip() if p.is_file() else ''

    add('python', select_version(home / '.pyenv/versions', read('.pyenv/version')), 'pyenv default resolved against installed versions')
    node = select_version(home / '.nvm/versions/node', read('.nvm/alias/default').removeprefix('v'), 'v')
    add('node', node, 'NVM default resolved against installed versions')
    go_version = read('.local/go/VERSION').splitlines()
    if go_version:
        add('go', go_version[0].removeprefix('go'), 'Standalone Go VERSION metadata')
    vendors = {'tem': 'temurin', 'zulu': 'zulu', 'amzn': 'corretto', 'librca': 'liberica', 'open': 'openjdk', 'graal': 'graalvm'}
    for candidate, name in [('java', 'java'), ('maven', 'maven'), ('gradle', 'gradle'), ('kotlin', 'kotlin')]:
        current = home / '.sdkman/candidates' / candidate / 'current'
        if current.exists():
            value = current.resolve().name
            if candidate == 'java':
                match = re.fullmatch(r'(.+)-([a-z]+)', value)
                if not match or match[2] not in vendors:
                    deferred.append({'tool': candidate, 'version': value, 'reason': 'Unknown SDKMAN vendor; map to mise explicitly'})
                    continue
                value = vendors[match[2]] + '-' + match[1]
            add(name, value, 'SDKMAN current symlink')
    # Package metadata is portable. Never copy Linux executables or node_modules.
    modules = home / '.nvm/versions/node' / ('v' + (node or 'missing')) / 'lib/node_modules'
    for manifest in sorted([*modules.glob('*/package.json'), *modules.glob('@*/*/package.json')]):
        data = json.loads(manifest.read_text())
        name, version = data.get('name', ''), data.get('version')
        if not data.get('bin'):
            continue
        if name in {'npm', 'corepack'}:
            deferred.append({'tool': name, 'version': version, 'reason': 'npm bundled with mise Node; corepack replaced by mise pnpm'})
            continue
        if not re.fullmatch(r'(?:@[a-z0-9._-]+/)?[a-z0-9._-]+', name):
            continue
        key = name if name in {'bun', 'deno', 'pnpm', 'supabase'} else 'npm:' + name
        add(key, version, 'Global Node package.json (CLI package)')
    # Installed Python distributions: entrypoint owner from uv receipts, version from METADATA.
    for receipt in sorted((home / '.local/share/uv/tools').glob('*/uv-receipt.toml')):
        import tomllib
        spec = tomllib.loads(receipt.read_text())['tool']['requirements'][0]
        name = spec['name']
        if spec.get('git'):
            match = re.fullmatch(r'https://github.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\.git\?rev=([A-Za-z0-9_.-]+)', spec['git'])
            if match:
                add('pypi:' + match[1], match[2], 'uv Git receipt pinned tag')
            else:
                deferred.append({'tool': name, 'reason': 'Git-based Python tool needs target URL mapping; inspect original local receipt'})
            continue
        version = None
        for metadata in receipt.parent.glob('lib/python*/site-packages/*.dist-info/METADATA'):
            data = metadata.read_text(errors='replace')
            installed_name = re.search(r'^Name: (.+)$', data, re.M)
            installed_version = re.search(r'^Version: (.+)$', data, re.M)
            if installed_name and installed_version and installed_name[1].lower().replace('_', '-') == name.lower().replace('_', '-'):
                version = installed_version[1]
                break
        add(name if name in {'ruff', 'ty'} else 'pypi:' + name, version, 'uv tool receipt and distribution METADATA')
    go = home / '.local/go/bin/go'
    if go.is_file():
        for binary in sorted((home / 'go/bin').glob('*')):
            if not binary.is_file():
                continue
            r = subprocess.run([str(go), 'version', '-m', str(binary)], capture_output=True, text=True, timeout=20)
            path = re.search(r'^\s*path\s+(\S+)', r.stdout, re.M)
            mod = re.search(r'^\s*mod\s+(\S+)\s+(v[^\s]+)', r.stdout, re.M)
            if not path or not mod:
                continue
            if not path[1].startswith(('github.com/', 'golang.org/', 'google.golang.org/')):
                deferred.append({'tool': binary.name, 'version': mod[2], 'reason': 'Private/non-allowlisted Go module needs target authentication', 'mise_tool': 'go:' + path[1]})
            else:
                add('go:' + path[1], mod[2], 'Go build metadata (binary was not executed)')
    # Known portable CLIs. Only probe --version for these trusted executables.
    probes = {'uv': ('uv', '--version'), 'fzf': ('fzf', '--version'), 'zoxide': ('zoxide', '--version'),
              'jq': ('jq', '--version'), 'gh': ('gh', '--version'), 'ripgrep': ('rg', '--version'),
              'kubectl': ('kubectl', 'version', '--client=true', '--output=json'),
              'helm': ('helm', 'version', '--short'), 'protoc': ('protoc', '--version'),
              'glow': ('glow', '--version'), 'helix': ('hx', '--version'),
              'docker-cli': ('docker', '--version'), 'rtk': ('rtk', '--version'),
              'github:exercism/cli': ('exercism', 'version'),
              'eza': ('eza', '--version'),
              'bat': ('bat' if shutil.which('bat') else 'batcat', '--version')}
    for key, argv in probes.items():
        command = shutil.which(argv[0])
        if not command:
            continue
        try:
            result = subprocess.run([command, *argv[1:]], capture_output=True, text=True, timeout=10)
            match = re.search(r'\b(?:v)?(\d+\.\d+(?:\.\d+)?)(?:\b)', result.stdout)
            if result.returncode == 0 and match:
                version = match[1]
                # Protobuf 3.21.x reports a language version; GitHub binary tags are v21.x.
                if key == 'protoc' and version.startswith('3.21.'):
                    version = version.removeprefix('3.')
                add(key, version, 'Source CLI version probe' + ('; protobuf 3.21.x maps to release 21.x' if key == 'protoc' else ''))
        except subprocess.TimeoutExpired:
            deferred.append({'tool': key, 'reason': 'Source version probe timed out'})
    claude = home / '.local/bin/claude'
    if claude.is_symlink():
        add('claude-code', claude.resolve().name, 'Claude native installation symlink')
    # Inventory remaining local executables without running unknown scripts.
    known_local = {'claude', 'copilot', 'debugpy', 'debugpy-adapter', 'exercism', 'graphify',
                   'graphify-mcp', 'ruff', 'specify', 'ty', 'uv', 'uvx', 'zoxide', 'rtk'}
    for binary in sorted((home / '.local/bin').glob('*')):
        if binary.name not in known_local and binary.is_file():
            reason = ('Legacy Go updater replaced by mise upgrade go' if binary.name in {'go-upgrade', 'upgrade-go'}
                      else 'Custom/platform application: choose mise backend on target; executable not copied')
            deferred.append({'tool': binary.name, 'reason': reason})
    return {'tools': tools, 'evidence': evidence, 'deferred': deferred,
            'policy': 'All development tools/environments are installed through mise; native packages only for bootstrap and unavoidable system dependencies.'}


def write(home, config, package):
    report = collect(home)
    config.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# Generated source tool versions. Edit intentionally for the target.', '[settings]',
             'auto_install = false', 'idiomatic_version_file_enable_tools = ["node", "python", "java"]', '', '[tools]']
    for tool, version in sorted(report['tools'].items()):
        lines.append(json.dumps(tool) + ' = ' + json.dumps(version))
    config.write_text('\n'.join(lines) + '\n')
    shutil.copy2(config, package / 'mise-tools.toml')
    (package / 'development-tools.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
