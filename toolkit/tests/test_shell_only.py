#!/usr/bin/env python3
"""Public shell-only installation, bootstrap isolation, startup and rollback."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]
PACKAGE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else KIT
ZSH = shutil.which('zsh')
BASH = shutil.which('bash')


class ShellOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='shell only migration ')
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home with spaces'
        self.home.mkdir()
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.env = {'HOME': str(self.home), 'PATH': str(self.bin) + ':/usr/bin:/bin',
                    'USER': 'migration-test', 'LOGNAME': 'migration-test',
                    'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8',
                    'LOG': str(self.base / 'unexpected-installs')}
        for tool in ['mise', 'sudo', 'curl', 'wget']:
            p = self.bin / tool
            p.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$LOG"\nexit 99\n')
            p.chmod(0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def run_wrapper(self, *args, env=None):
        return subprocess.run([BASH, str(PACKAGE / 'migrate-zsh.sh'), *args],
                              env=env or self.env, cwd=self.base,
                              capture_output=True, text=True, timeout=60)

    def assert_success(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_dry_run_has_no_home_or_installer_changes(self):
        r = self.run_wrapper('--dry-run')
        self.assert_success(r)
        self.assertIn('Scope: Zsh', r.stdout)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse((self.base / 'unexpected-installs').exists())
        self.assertNotIn('\n.config/mise/config.toml\n', r.stdout)

    def test_existing_runtime_configuration_survives_restore_startup_and_rollback(self):
        if os.geteuid() == 0:
            self.skipTest('Restore intentionally refuses root')
        config = self.home / '.config/mise/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('[tools]\nnode="22"\n')
        (self.home / '.zshrc').write_text('# original shell\n')
        (self.home / '.zsh_history').write_text('target history\n')
        self.env.update(MISE_GLOBAL_CONFIG_FILE=str(config), JAVA_HOME='/native/java',
                        PYENV_ROOT='/native/pyenv', GO111MODULE='off')
        r = self.run_wrapper()
        self.assert_success(r)
        self.assertEqual(config.read_text(), '[tools]\nnode="22"\n')
        backups = list((self.home / '.zsh-migration-backups').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertNotIn('.config/mise/config.toml', (backups[0] / 'managed-paths.txt').read_text())
        for mode in ['-ic', '-lic']:
            r = subprocess.run([ZSH, mode, '''
[[ $JAVA_HOME == /native/java && $PYENV_ROOT == /native/pyenv && $GO111MODULE == off ]] || exit 1
for fn in _zsh_autosuggest_start _zsh_highlight history-substring-search-up zinit; do
  (( $+functions[$fn] )) || exit 2
done
[[ $ZSH_THEME == robbyrussell ]] || exit 3
print SHELL_OK
'''], env=self.env, cwd=self.home, capture_output=True, text=True, timeout=45)
            self.assert_success(r)
            self.assertEqual(r.stderr, '')
        r = subprocess.run([ZSH, '-f', str(PACKAGE / 'verify.zsh')], env=self.env,
                           cwd=self.home, capture_output=True, text=True, timeout=60)
        self.assert_success(r)
        self.assertIn('Scope: shell-only', r.stdout)
        self.assertNotIn('mise ownership', r.stdout)
        self.assertFalse((self.base / 'unexpected-installs').exists())
        config.write_text('# later runtime change\n')
        r = subprocess.run([ZSH, '-f', str(PACKAGE / 'rollback.zsh'), str(backups[0])],
                           env=self.env, capture_output=True, text=True, timeout=60)
        self.assert_success(r)
        self.assertEqual(config.read_text(), '# later runtime change\n')
        self.assertEqual((self.home / '.zshrc').read_text(), '# original shell\n')
        self.assertEqual((self.home / '.zsh_history').read_text(), 'target history\n')

    def test_fresh_shell_only_restore_creates_no_mise_configuration(self):
        if os.geteuid() == 0:
            self.skipTest('Restore intentionally refuses root')
        self.assert_success(self.run_wrapper())
        self.assertFalse((self.home / '.config/mise').exists())
        self.assertTrue((self.home / '.oh-my-zsh/oh-my-zsh.sh').is_file())
        self.assertTrue((self.home / '.local/share/zinit/zinit.git/zinit.zsh').is_file())
        self.assertEqual((self.home / '.config/zsh-migration/scope').read_text(), 'shell-only\n')
        self.assertFalse((self.base / 'unexpected-installs').exists())

    def test_missing_zsh_bootstrap_installs_only_zsh(self):
        if os.geteuid() == 0 or sys.platform != 'linux':
            self.skipTest('Linux bootstrap requires a normal user')
        # No zsh in PATH initially. sudo is a stub that supplies it after install.
        for name in ['bash', 'dirname', 'sha256sum', 'id', 'uname', 'mktemp', 'tar',
                     'gzip', 'rm', 'sed', 'mv', 'cat', 'mkdir', 'chmod', 'date', 'cp']:
            (self.bin / name).symlink_to(shutil.which(name))
        apt = self.bin / 'apt-get'
        apt.write_text('#!/bin/sh\nexit 0\n')
        apt.chmod(0o700)
        sudo = self.bin / 'sudo'
        sudo.write_text('''#!/bin/sh
printf '%s\n' "$*" >> "$LOG"
case "$*" in
  'apt-get install -y zsh') /bin/ln -s "$REAL_ZSH" "$TEST_BIN/zsh" ;;
  'apt-get update') ;;
  *) exit 99 ;;
esac
''')
        sudo.chmod(0o700)
        env = dict(self.env, PATH=str(self.bin), REAL_ZSH=ZSH, TEST_BIN=str(self.bin))
        self.assert_success(self.run_wrapper(env=env))
        self.assertEqual((self.base / 'unexpected-installs').read_text().splitlines(),
                         ['apt-get update', 'apt-get install -y zsh'])
        self.assertFalse((self.home / '.config/mise').exists())
        self.assertTrue((self.home / '.oh-my-zsh/oh-my-zsh.sh').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
