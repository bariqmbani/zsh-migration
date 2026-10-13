#!/usr/bin/env python3
"""Create a sanitized, self-contained package. Does not source shell config."""
import argparse
import importlib.util
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile

KIT = Path(__file__).resolve().parent
SECRET_NAME = re.compile(r'(api_?key|token|password|passwd|secret|credential)', re.I)
ASSIGNMENT = re.compile(r'^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z_0-9]*)(\s*=\s*)(.*)$')
TOKEN = re.compile(rb'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}\b')
BINARY_MAGIC = (b'\x7fELF', b'MZ', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca')
ROOTS = ['.zshrc', '.zprofile', '.zshenv', '.zlogin', '.zlogout', '.fzf.zsh',
         '.oh-my-zsh', '.local/share/zinit', '.fzf', '.zfunc', '.config/zsh_codex.ini',
         '.profile', '.bashrc', '.bash_logout', '.shell.pre-oh-my-zsh']
MANAGED = ['.zshenv', '.zprofile', '.zshrc', '.zlogin', '.zlogout', '.fzf.zsh',
           '.oh-my-zsh', '.local/share/zinit', '.config/zsh-migration',
           '.config/zsh_codex.ini', '.config/mise/config.toml']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def personal_config(rel):
    return len(rel.parts) == 1 or str(rel) == '.config/zsh_codex.ini'


def get_secrets(home, roots):
    found = set()
    for rel in roots:
        p = home / rel
        if not p.is_file() or not personal_config(Path(rel)):
            continue
        for line in p.read_text(errors='replace').splitlines():
            m = ASSIGNMENT.match(line)
            if m and SECRET_NAME.search(m[2]):
                value = m[4].strip().strip('"\'')
                if value and not any(x in value for x in ('$', '`', ' ', '#')):
                    found.add(value.encode())
        found.update(TOKEN.findall(p.read_bytes()))
    return sorted(found, key=len, reverse=True)


def sanitize(data, rel, secrets):
    for secret in secrets:
        data = data.replace(secret, b'REDACTED')
    data = TOKEN.sub(b'REDACTED', data)
    if personal_config(rel):
        text = data.decode('utf-8')
        lines = []
        for line in text.splitlines(keepends=True):
            m = ASSIGNMENT.match(line.rstrip('\n'))
            if m and SECRET_NAME.search(m[2]):
                value = '' if rel.suffix == '.ini' else "'' # credential excluded from migration"
                line = m[1] + m[2] + m[3] + value + '\n'
            lines.append(line)
        data = ''.join(lines).encode()
    return data


def skip(rel):
    return (any(part in {'.git', '__pycache__', '.cache', 'cache', '.pytest_cache'} for part in rel.parts)
            or rel.name.endswith(('.zwc', '.zwc.old', '.pyc', '.log'))
            or rel.name.startswith(('.zcompdump', '.zsh_history', '.env'))
            or rel.name in {'.zsh-update', '.zsh_sessions', 'db.zo'})


def git_info(p):
    def git(*args):
        r = subprocess.run(['git', '-C', str(p), *args], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    url = git('remote', 'get-url', 'origin')
    if url:
        url = re.sub(r'(https?://)[^/@]+@', r'\1', url).split('?', 1)[0]
    return {'commit': git('rev-parse', 'HEAD'), 'upstream': url,
            'modified_tracked_files': git('diff', '--name-only', 'HEAD')}


def snapshot(home, roots, destination, secrets):
    inventory, exclusions, repositories = [], [], {}
    def copy(p, rel):
        if skip(rel):
            exclusions.append({'path': str(rel), 'reason': 'metadata/cache/history/private env'})
            return
        out = destination / rel
        mode = stat.S_IMODE(p.lstat().st_mode)
        entry = {'path': str(rel), 'source_mode': oct(mode)}
        if p.is_symlink():
            target = os.readlink(p)
            resolved = (p.parent / target).resolve()
            try:
                resolved_rel = resolved.relative_to(home)
            except ValueError:
                exclusions.append({'path': str(rel), 'reason': 'symlink outside source HOME'})
                return
            out.parent.mkdir(parents=True, exist_ok=True)
            # Convert even chained absolute Zinit links into relocatable links.
            new_target = os.path.relpath(destination / resolved_rel, out.parent)
            out.symlink_to(new_target)
            entry.update(type='symlink', source_target=target, target=new_target)
        elif p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            out.chmod(mode & 0o755)
            if (p / '.git').exists():
                repositories[str(rel)] = git_info(p)
            entry['type'] = 'directory'
            for child in sorted(p.iterdir()):
                copy(child, rel / child.name)
        elif p.is_file():
            data = p.read_bytes()
            if data.startswith(BINARY_MAGIC):
                exclusions.append({'path': str(rel), 'reason': 'architecture-specific executable'})
                return
            cleaned = sanitize(data, rel, secrets)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(cleaned)
            out.chmod((mode & 0o755) if mode & 0o111 else 0o600)
            entry.update(type='file', bytes=len(cleaned), sha256=sha(cleaned), sanitized=data != cleaned)
        else:
            exclusions.append({'path': str(rel), 'reason': 'special filesystem entry'})
            return
        inventory.append(entry)
    for rel in roots:
        p = home / rel
        if p.exists() or p.is_symlink():
            copy(p, Path(rel))
    for link in destination.rglob('*'):
        if link.is_symlink() and not link.exists():
            exclusions.append({'path': str(link.relative_to(destination)), 'reason': 'broken link or target excluded'})
            link.unlink()
    return inventory, exclusions, repositories


def make_tar(tree, output):
    def metadata(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ''
        return info
    with tarfile.open(output, 'w:gz', format=tarfile.PAX_FORMAT, dereference=False) as tf:
        for p in sorted(tree.iterdir()):
            tf.add(p, arcname=p.name, filter=metadata)


def validate_tree(tree, secrets):
    count = 0
    names = set()
    for p in tree.rglob('*'):
        folded = str(p.relative_to(tree)).casefold()
        if folded in names:
            raise RuntimeError('Case-insensitive filesystem collision: ' + str(p.relative_to(tree)))
        names.add(folded)
        if p.is_symlink():
            target = p.resolve()
            if not target.is_relative_to(tree) or not target.exists():
                raise RuntimeError('Unresolved or escaping packaged link: ' + str(p.relative_to(tree)))
        elif p.is_file():
            data = p.read_bytes()
            if any(s in data for s in secrets) or TOKEN.search(data):
                raise RuntimeError('Credential scan failed for ' + str(p.relative_to(tree)))
            if data.startswith(BINARY_MAGIC):
                raise RuntimeError('Architecture-specific executable in payload')
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-home', type=Path, default=Path.home())
    parser.add_argument('--output-dir', type=Path, default=KIT.parent / 'dist')
    args = parser.parse_args()
    home = args.source_home.resolve()
    for required in ['.zshrc', '.oh-my-zsh/oh-my-zsh.sh', '.local/share/zinit/zinit.git/zinit.zsh']:
        if not (home / required).is_file():
            raise SystemExit('This source profile requires ' + required + '; see README source scope.')
    roots = list(ROOTS)
    for pattern in ('.zshrc.*', '.zprofile.*', '.zshenv.*', '.zlogin.*', '.zlogout.*', '.fzf.zsh.*'):
        roots.extend(str(p.relative_to(home)) for p in home.glob(pattern) if p.is_file())
    roots = sorted(set(roots))
    secrets = get_secrets(home, roots)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = 'zsh-migration-' + stamp
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    final = output_dir / name
    zip_path = output_dir / (name + '.zip')
    if final.exists() or zip_path.exists():
        raise SystemExit('Output already exists; retry with a new timestamp.')
    with tempfile.TemporaryDirectory(prefix='zsh-migration-build-') as tmp:
        work = Path(tmp)
        package = work / name
        # Only explicitly maintained kit files; never pull unrelated migration data.
        shutil.copytree(KIT, package, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        source = work / 'source'
        source.mkdir()
        inventory, exclusions, repositories = snapshot(home, roots, source, secrets)
        system_dir = source / 'system-reference/etc/zsh'
        if Path('/etc/zsh').is_dir():
            system_dir.mkdir(parents=True)
            for p in Path('/etc/zsh').iterdir():
                if p.is_file():
                    data = p.read_bytes()
                    cleaned = sanitize(data, Path(p.name), secrets)
                    (system_dir / p.name).write_bytes(cleaned)
                    inventory.append({'path': 'system-reference/etc/zsh/' + p.name,
                                      'type': 'file', 'source_mode': oct(stat.S_IMODE(p.stat().st_mode)),
                                      'bytes': len(cleaned), 'sha256': sha(cleaned), 'sanitized': data != cleaned})
        payload = work / 'payload'
        payload.mkdir()
        for rel in ('.oh-my-zsh', '.local/share/zinit', '.zfunc', '.config/zsh_codex.ini'):
            src, dst = source / rel, payload / rel
            if not src.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst)
        # Preserve WSL-specific helpers in source only; OMZ auto-sources custom/*.zsh.
        for p in (payload / '.oh-my-zsh/custom').glob('kiro*.zsh'):
            p.unlink()
        spec = importlib.util.spec_from_file_location('collect_tools', KIT / 'collect-tools.py')
        collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(collector)
        development = collector.write(home, payload / '.config/mise/config.toml', package)
        config = payload / '.config/zsh-migration'
        config.mkdir(parents=True)
        for template, dest in [('zshrc', '.zshrc'), ('zprofile', '.zprofile'), ('fzf.zsh', '.fzf.zsh'),
                               ('environment.zsh', '.config/zsh-migration/environment.zsh'),
                               ('aliases.zsh', '.config/zsh-migration/aliases.zsh'),
                               ('secrets.example.zsh', '.config/zsh-migration/secrets.example.zsh')]:
            shutil.copy2(KIT / 'templates' / template, payload / dest)
        for name_rc in ('.zshenv', '.zlogin', '.zlogout'):
            (payload / name_rc).write_text('# Migration placeholder: original target file was backed up.\n')
        source_rc = (source / '.zshrc').read_text()
        plugin_match = re.search(r'^plugins=\((.*?)\)', source_rc, re.M | re.S)
        theme_match = re.search(r'^ZSH_THEME=(.*)$', source_rc, re.M)
        if not plugin_match or not theme_match:
            raise SystemExit('Source needs literal plugins=(...) and ZSH_THEME=... declarations.')
        plugins = shlex.split(plugin_match[1], comments=True)
        theme_tokens = shlex.split(theme_match[1], comments=True)
        if len(theme_tokens) != 1 or not all(re.fullmatch(r'[A-Za-z0-9_.+-]+', x) for x in plugins + theme_tokens):
            raise SystemExit('Dynamic plugin/theme declarations require manual profile adaptation.')
        theme = theme_tokens[0]
        profile = {'theme': theme, 'plugins': plugins}
        (package / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
        (config / 'profile.zsh').write_text('ZSH_THEME=' + shlex.quote(theme) + '\nplugins=(' + ' '.join(map(shlex.quote, plugins)) + ')\n')
        portable = []
        portable_exports = {'GOPROXY', 'GO111MODULE', 'CGO_LDFLAGS_ALLOW', 'GOLANG_PROTOBUF_REGISTRATION_CONFLICT'}
        for line in source_rc.splitlines():
            if line.startswith('alias '):
                tokens = shlex.split(line, comments=True)
                if len(tokens) == 2 and '=' in tokens[1]:
                    alias_name, command = tokens[1].split('=', 1)
                    if re.fullmatch(r'[A-Za-z0-9_-]+', alias_name) and alias_name not in {'alert', 'code', 'kiro'} and not any(x in command for x in ['/mnt/', '/home/', '.exe', 'REDACTED']):
                        portable.append('alias ' + alias_name + '=' + shlex.quote(command))
            match = ASSIGNMENT.match(line)
            if match and match[2] in portable_exports:
                values = shlex.split(match[4], comments=True)
                if len(values) == 1 and not any(x in values[0] for x in ['$', '`', 'REDACTED']):
                    portable.append('export ' + match[2] + '=' + shlex.quote(values[0]))
        (config / 'portable-settings.zsh').write_text('\n'.join(portable) + '\n')
        # Capture non-secret AI choices from source; never evaluate source shell code.
        ai_names = {'ZSH_AI_PROVIDER', 'ZSH_AI_OPENAI_URL', 'ZSH_AI_OPENAI_MODEL',
                    'ZSH_AI_TRIGGER', 'ZSH_AI_COMMENT_HOOK'}
        ai = []
        for line in (source / '.zshrc').read_text().splitlines():
            match = ASSIGNMENT.match(line)
            if match and match[2] in ai_names:
                value = match[4].strip()
                if any(c in value for c in ('`', '$', '\n', ';')):
                    raise RuntimeError('AI setting needs manual review: ' + match[2])
                ai.append(line)
        (config / 'ai-settings.zsh').write_text('\n'.join(ai) + '\n')
        local_completions = sorted(str(p.relative_to(payload)) for p in (payload / '.zfunc').rglob('*')
                                   if p.is_file() or p.is_symlink())
        managed = MANAGED + local_completions
        if not (payload / '.config/zsh_codex.ini').exists():
            managed.remove('.config/zsh_codex.ini')
        (package / 'managed-paths.txt').write_text('\n'.join(managed) + '\n')
        snapshot_count = validate_tree(source, secrets)
        payload_count = validate_tree(payload, secrets)
        # No private files or world/group-writable content in active payload.
        for p in payload.rglob('*'):
            if not p.is_symlink():
                p.chmod(0o700 if p.is_dir() else (0o700 if p.stat().st_mode & 0o111 else 0o600))
        make_tar(source, package / 'source-backup.tar.gz')
        make_tar(payload, package / 'payload.tar.gz')
        document = {
            'created_utc': stamp, 'source_home': str(home), 'source_kernel': os.uname().sysname,
            'targets': ['Linux', 'WSL', 'macOS (ARM64/Intel)', 'BSD (configuration-only, experimental)'],
            'source_zsh': subprocess.run(['zsh', '--version'], capture_output=True, text=True).stdout.strip(),
            'enabled_omz_plugins': plugins,
            'conditionally_enabled': {'zsh-ai': 'requires local API key'},
            'theme': theme, 'repositories': repositories, 'source_files': inventory,
            'excluded_entries': exclusions,
            'excluded_categories': ['credentials', 'command history', 'zoxide directory history', 'Git metadata',
                                    'generated caches/bytecode', 'architecture-specific executables', 'development runtime installations',
                                    'terminal emulator settings', 'unrelated application credentials'],
            'development_tools': development,
            'runtime_manager': 'mise',
            'shell_dependencies': ['zsh >=5.8', 'git', 'fzf', 'zoxide', 'jq', 'curl', 'perl'],
            'settings_not_activated': ['Windows launcher helpers', 'Proxy', 'GOPRIVATE', 'GOINSECURE', 'GIT_SSL_NO_VERIFY', 'non-allowlisted source startup logic'],
            'credential_values_redacted': len(secrets), 'snapshot_files_scanned': snapshot_count,
            'payload_files_scanned': payload_count,
            'mac_validation': 'PENDING: no Mac accessible from WSL',
        }
        (package / 'inventory.json').write_text(json.dumps(document, indent=2) + '\n')
        # Scan the human-readable package files as well as both archive inputs.
        for p in package.rglob('*'):
            if p.is_file() and p.suffix != '.gz':
                data = p.read_bytes()
                if any(s in data for s in secrets):
                    raise RuntimeError('Credential in package documentation')
        for p in package.rglob('*'):
            if p.is_file():
                p.chmod(0o700 if p.suffix in ('.sh', '.zsh', '.py') else 0o600)
        lines = []
        for p in sorted(package.rglob('*')):
            if p.is_file() and p.name != 'SHA256SUMS':
                lines.append(sha(p.read_bytes()) + '  ' + p.relative_to(package).as_posix())
        (package / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
        shutil.copytree(package, final)
        final.chmod(0o700)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(final.rglob('*')):
            if p.is_file():
                zf.write(p, p.relative_to(output_dir))
    zip_path.chmod(0o600)
    digest = sha(zip_path.read_bytes())
    sidecar = output_dir / (zip_path.name + '.sha256')
    sidecar.write_text(digest + '  ' + zip_path.name + '\n')
    sidecar.chmod(0o600)
    with zipfile.ZipFile(zip_path) as zf:
        if zf.testzip():
            raise RuntimeError('ZIP integrity verification failed')
    print(json.dumps({'package': str(final), 'zip': str(zip_path), 'sha256': digest,
                      'snapshot_files': snapshot_count, 'payload_files': payload_count}, indent=2))


if __name__ == '__main__':
    main()
