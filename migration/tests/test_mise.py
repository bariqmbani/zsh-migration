#!/usr/bin/env python3
"""Mise migration behavior without modifying the source or downloading runtimes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest

KIT = Path(__file__).resolve().parents[1]
PACKAGE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else KIT
ZSH = shutil.which('zsh')


class MiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mise migration test ')
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color',
                    'KIT': str(KIT), 'PACKAGE': str(PACKAGE), 'LOG': str(self.base / 'calls')}

    def tearDown(self):
        self.tmp.cleanup()

    def shell(self, code, check=True):
        r = subprocess.run([ZSH, '-fc', code], cwd=self.base, env=self.env,
                           capture_output=True, text=True, timeout=40)
        if check:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def extract(self):
        stage = self.base / 'stage'
        stage.mkdir()
        with tarfile.open(PACKAGE / 'payload.tar.gz') as tf:
            tf.extractall(stage, filter='data')
        self.env['STAGE'] = str(stage)
        return stage

    def stub(self):
        p = self.home / '.local/bin/mise'
        p.parent.mkdir(parents=True)
        p.write_text('''#!/bin/sh
printf '%s|%s|%s\n' "$*" "$MISE_GLOBAL_CONFIG_FILE" "${GOROOT:-unset}" >> "$LOG"
if [ "$1" = activate ]; then
  printf 'export MISE_TEST_ACTIVATED=1\n'
fi
exit "${FAIL_CODE:-0}"
''')
        p.chmod(0o700)

    def test_baseline_and_payload_config_match(self):
        stage = self.extract()
        raw = (PACKAGE / 'mise-tools.toml').read_bytes()
        self.assertEqual(raw, (stage / '.config/mise/config.toml').read_bytes())
        data = tomllib.loads(raw.decode())
        self.assertFalse(data['settings']['auto_install'])
        for tool in ['go', 'python', 'node', 'java', 'uv', 'pnpm', 'maven']:
            self.assertIn(tool, data['tools'])
        self.assertFalse({'nvm', 'pyenv', 'sdkman', 'asdf', 'corepack'} & data['tools'].keys())
        self.assertIn('.config/mise/config.toml', (PACKAGE / 'managed-paths.txt').read_text().splitlines())
        report = json.loads((PACKAGE / 'development-tools.json').read_text())
        self.assertEqual(report['tools'], data['tools'])

    def test_user_policy_survives_source_rediscovery(self):
        spec = importlib.util.spec_from_file_location('collector', KIT / 'collect-tools.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = {'tools': {'go': '99.0.0', 'uv': '0.1.0', 'ruff': '0.1.0', 'ty': '0.1.0',
                            'rtk': '0.1.0', 'github:exercism/cli': '99.0.0',
                            'npm:@github/copilot': '99.0.0', 'new-tool': '1.0.0'},
                  'evidence': {}, 'deferred': []}
        report = module.apply_policy(source)
        self.assertEqual(report['tools']['go'], '1.27.1')
        self.assertEqual(report['tools']['python'], '3.13.14')
        self.assertEqual(report['tools']['java'], 'temurin-26.0.1')
        for name in ['uv', 'ruff', 'ty']:
            self.assertEqual(report['tools'][name], 'latest')
        self.assertEqual(len(report['tools']), 17)
        self.assertEqual(len(report['manual_tools']), 19)
        self.assertEqual(report['manual_tools']['yq']['version'], 'latest')
        self.assertEqual(report['manual_tools']['rtk']['version'], 'latest')
        self.assertNotIn('rtk', report['tools'])
        self.assertNotIn('github:exercism/cli', report['tools'])
        self.assertNotIn('npm:@github/copilot', report['manual_tools'])
        self.assertNotIn('new-tool', report['tools'])
        self.assertTrue(any(x['tool'] == 'new-tool' for x in report['deferred']))
        package_report = json.loads((PACKAGE / 'development-tools.json').read_text())
        policy = json.loads((KIT / 'tool-policy.json').read_text())
        self.assertEqual(package_report['tools'], policy['mise'])
        self.assertFalse(set(package_report['tools']) & set(policy['excluded']))
        self.assertFalse(set(package_report['manual_tools']) & set(policy['excluded']))
        self.assertEqual((PACKAGE / 'manual-commands.txt').read_text().splitlines(),
                         ['|'.join(x['commands']) for x in package_report['manual_tools'].values()])

    def test_metadata_mapping_resolves_defaults_and_vendor(self):
        spec = importlib.util.spec_from_file_location('collector', KIT / 'collect-tools.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for v in ['3.13.1', '3.13.14', '3.14.6']:
            (self.home / '.pyenv/versions' / v).mkdir(parents=True)
        (self.home / '.pyenv/version').write_text('3.13\n')
        for v in ['v22.23.1', 'v24.16.0']:
            (self.home / '.nvm/versions/node' / v).mkdir(parents=True)
        (self.home / '.nvm/alias').mkdir()
        (self.home / '.nvm/alias/default').write_text('24\n')
        java = self.home / '.sdkman/candidates/java'
        (java / '26.0.1-tem').mkdir(parents=True)
        (java / 'current').symlink_to('26.0.1-tem')
        result = module.collect(self.home)['tools']
        self.assertEqual(result['python'], '3.13.14')
        self.assertEqual(result['node'], '24.16.0')
        self.assertEqual(result['java'], 'temurin-26.0.1')

    def test_install_routes_all_tools_through_mise(self):
        self.extract()
        self.stub()
        self.env['GOROOT'] = '/legacy/go'
        self.shell('''source "$KIT/lib/platform.zsh"
MIGRATION_PLATFORM=linux
MIGRATION_MANAGER=manual
migration_missing_dependencies() { MIGRATION_MISSING=(); }
migration_install_dependencies "$STAGE"
''')
        lines = (self.base / 'calls').read_text().splitlines()
        self.assertEqual([x.split('|')[0] for x in lines],
                         ['install go python node java uv pnpm maven', 'install', 'reshim'])
        self.assertTrue(all('|unset' in x and '/stage/.config/mise/config.toml|' in x for x in lines))
        self.assertFalse((self.home / '.zshrc').exists())
        self.assertFalse((self.home / '.config/mise/config.toml').exists())

    def test_failed_mise_install_preserves_target_config(self):
        self.stub()
        (self.home / '.zshrc').write_text('original shell\n')
        config = self.home / '.config/mise/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('[tools]\nnode="20"\n')
        self.env['FAIL_CODE'] = '42'
        r = self.shell('zsh -f "$PACKAGE/restore.zsh"', check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.home / '.zshrc').read_text(), 'original shell\n')
        self.assertEqual(config.read_text(), '[tools]\nnode="20"\n')
        self.assertEqual(len((self.base / 'calls').read_text().splitlines()), 1)
        self.assertFalse((self.home / '.zsh-migration-backups').exists())

    def test_existing_mise_config_is_restored_by_rollback(self):
        self.extract()
        config = self.home / '.config/mise/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('[tools]\nnode="20"\n')
        self.shell('''source "$KIT/lib/migration.zsh"
migration_apply "$STAGE" "$PACKAGE/managed-paths.txt" || exit 1
migration_rollback "$MIGRATION_BACKUP" || exit 2
''')
        self.assertEqual(config.read_text(), '[tools]\nnode="20"\n')

    def test_legacy_paths_cleaned_and_only_mise_activated(self):
        stage = self.extract()
        shutil.copytree(stage, self.home, dirs_exist_ok=True, symlinks=True)
        self.stub()
        self.env.update(PATH=str(self.home / '.nvm/versions/node/old/bin') + ':' +
                        str(self.home / '.pyenv/shims') + ':/custom/pyenv/bin:/usr/bin:/bin',
                        PYENV_ROOT='/custom/pyenv', NVM_DIR=str(self.home / '.nvm'),
                        JAVA_HOME='/legacy/java', GOROOT='/legacy/go')
        r = subprocess.run([ZSH, '-ic', '''
[[ $MISE_TEST_ACTIVATED == 1 ]] || exit 1
[[ $PATH != *'.nvm/'* && $PATH != *'.pyenv/'* && $PATH != *'/custom/pyenv'* ]] || exit 2
[[ -z ${NVM_DIR:-}${PYENV_ROOT:-}${JAVA_HOME:-}${GOROOT:-} ]] || exit 3
'''], env=self.env, cwd=self.home, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len((self.base / 'calls').read_text().splitlines()), 1)
        self.assertIn('activate zsh|', (self.base / 'calls').read_text())

    def test_custom_config_override_stops_before_install(self):
        self.env['XDG_CONFIG_HOME'] = str(self.base / 'custom')
        r = self.shell('zsh -f "$PACKAGE/restore.zsh" --skip-deps', check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('XDG_CONFIG_HOME', r.stderr)
        self.assertFalse((self.home / '.zshrc').exists())

    def test_batcat_alias_preserves_spaces_and_piped_input(self):
        real_bat = shutil.which('batcat') or shutil.which('bat')
        if not real_bat:
            self.skipTest('Native bat/batcat needed for alias compatibility test')
        # Exercise both executable naming conventions against a real bat binary.
        sample = self.base / 'file with spaces.txt'
        sample.write_text('first line\nsecond line\n')
        self.env['SAMPLE'] = str(sample)
        for executable in ['bat', 'batcat']:
            with self.subTest(executable=executable):
                bindir = self.base / executable
                bindir.mkdir()
                (bindir / executable).symlink_to(real_bat)
                self.env['PATH'] = str(bindir)
                r = self.shell('''source "$KIT/templates/aliases.zsh"
eval 'cat "$SAMPLE"'
print -r -- 'piped input' | eval cat
''')
                self.assertEqual(r.stdout, 'first line\nsecond line\npiped input\n')
                self.assertEqual(r.stderr, '')

    @unittest.skipUnless(os.environ.get('MISE_TEST_BINARY'), 'Set MISE_TEST_BINARY for real mise offline parsing')
    def test_real_mise_parses_config_offline(self):
        self.env['MISE_GLOBAL_CONFIG_FILE'] = str(PACKAGE / 'mise-tools.toml')
        binary = os.environ['MISE_TEST_BINARY']
        r = subprocess.run([binary, 'ls', '--json', '--offline'], env=self.env, cwd=self.base,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        expected = tomllib.loads((PACKAGE / 'mise-tools.toml').read_text())['tools']
        # Offline mise omits unresolved floating selectors (e.g. Maven latest).
        pinned = {key for key, version in expected.items() if version != 'latest'}
        self.assertTrue(pinned <= set(data))
        self.assertTrue(set(data) <= set(expected))
        for key in expected:
            if ':' not in key:
                result = subprocess.run([binary, 'registry', key], env=self.env, cwd=self.base,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, key + ': ' + result.stderr)
                self.assertTrue(result.stdout.strip(), key)


if __name__ == '__main__':
    unittest.main(verbosity=2)
