#!/usr/bin/env python3
"""WSL tests of archive integrity, isolated startup and portable file transactions."""
import hashlib
import os
from pathlib import Path
import pty
import shutil
import subprocess
import sys
import tarfile
import tempfile
import re
import unittest

KIT = Path(__file__).resolve().parents[1]
PACKAGE = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else KIT
ZSH = shutil.which('zsh')


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='zsh-migration-test ')
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home with spaces'
        self.home.mkdir(mode=0o700)
        self.env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'USER': 'migration-test',
                    'LOGNAME': 'migration-test', 'TERM': 'xterm-256color', 'SHELL': ZSH,
                    'LC_ALL': 'C.UTF-8', 'KIT': str(KIT)}

    def tearDown(self):
        self.tmp.cleanup()

    def shell(self, code, check=True):
        r = subprocess.run([ZSH, '-f', '-c', 'source "$KIT/lib/migration.zsh"\n' + code],
                           env=self.env, cwd=self.home, capture_output=True, text=True, timeout=45)
        if check:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def fixture(self):
        tree = self.base / 'payload'
        tree.mkdir()
        (tree / '.zshrc').write_text('new shell\n')
        (tree / '.plugins').mkdir()
        (tree / '.plugins/plugin.zsh').write_text('new plugin\n')
        (tree / '.plugins/link').symlink_to('plugin.zsh')
        manifest = self.base / 'managed-paths.txt'
        manifest.write_text('.zshrc\n.plugins\n')
        self.env.update(TREE=str(tree), MANIFEST=str(manifest))
        return tree

    def test_fresh_install_and_rollback_preserves_later_edits(self):
        self.fixture()
        (self.home / '.zsh_history').write_text('existing target history\n')
        self.shell('''
            migration_apply "$TREE" "$MANIFEST" || exit 1
            [[ -L "$HOME/.plugins/link" ]] || exit 2
            print 'later edit' >> "$HOME/.zshrc"
            migration_rollback "$MIGRATION_BACKUP" || exit 3
            [[ ! -e "$HOME/.zshrc" && ! -e "$HOME/.plugins" ]] || exit 4
            migration_rollback "$MIGRATION_BACKUP" || exit 5
        ''')
        self.assertEqual((self.home / '.zsh_history').read_text(), 'existing target history\n')
        saved = list(self.home.glob('.zsh-migration-backups/*/rollback-saved-*/.zshrc'))
        self.assertEqual(len(saved), 1)
        self.assertIn('later edit', saved[0].read_text())

    def test_existing_symlink_and_directory_restored_on_repeat(self):
        self.fixture()
        original = self.base / 'original shell'
        original.write_text('original\n')
        (self.home / '.zshrc').symlink_to(original)
        (self.home / '.plugins').mkdir()
        (self.home / '.plugins/old').write_text('old\n')
        self.shell('''
            migration_apply "$TREE" "$MANIFEST" || exit 1
            first=$MIGRATION_BACKUP
            migration_apply "$TREE" "$MANIFEST" || exit 2
            second=$MIGRATION_BACKUP
            [[ $first != $second ]] || exit 3
            migration_rollback "$first" && exit 4
            migration_rollback "$second" || exit 5
            migration_rollback "$first" || exit 6
            [[ -L "$HOME/.zshrc" && -f "$HOME/.plugins/old" ]] || exit 7
        ''')
        self.assertEqual(original.read_text(), 'original\n')

    def test_symlink_parent_rejected_without_changes(self):
        tree = self.base / 'payload'
        (tree / '.config').mkdir(parents=True)
        (tree / '.config/file').write_text('new')
        outside = self.base / 'outside'
        outside.mkdir()
        (self.home / '.config').symlink_to(outside)
        manifest = self.base / 'managed'
        manifest.write_text('.config/file\n')
        self.env.update(TREE=str(tree), MANIFEST=str(manifest))
        r = self.shell('migration_apply "$TREE" "$MANIFEST"', check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((outside / 'file').exists())
        self.assertFalse((self.home / '.zsh-migration-backups').exists())

    def test_interrupted_activation_can_be_rolled_back(self):
        self.fixture()
        (self.home / '.zshrc').write_text('original')
        bindir = self.base / 'bin'
        bindir.mkdir()
        wrapper = bindir / 'mv'
        wrapper.write_text('#!/bin/sh\ncase "$1" in */prepared/.plugins) exit 73;; esac\nexec /bin/mv "$@"\n')
        wrapper.chmod(0o700)
        self.env['PATH'] = str(bindir) + ':/usr/bin:/bin'
        self.shell('''
            migration_apply "$TREE" "$MANIFEST" && exit 1
            [[ -n $MIGRATION_BACKUP ]] || exit 2
            migration_rollback "$MIGRATION_BACKUP" || exit 3
            [[ $(<"$HOME/.zshrc") == original && ! -e "$HOME/.plugins" ]] || exit 4
        ''')

    def test_backup_failure_does_not_activate_anything(self):
        self.fixture()
        (self.home / '.zshrc').write_text('original')
        bindir = self.base / 'bin'
        bindir.mkdir()
        wrapper = bindir / 'cp'
        wrapper.write_text('#!/bin/sh\ncase "$*" in *prepared/.plugins*) exit 74;; esac\nexec /bin/cp "$@"\n')
        wrapper.chmod(0o700)
        self.env['PATH'] = str(bindir) + ':/usr/bin:/bin'
        self.shell('''
            migration_apply "$TREE" "$MANIFEST" && exit 1
            [[ $(<"$HOME/.zshrc") == original && ! -e "$HOME/.plugins" ]] || exit 2
        ''')

    def test_package_integrity_and_payload_portability(self):
        for line in (PACKAGE / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest(), digest, name)
        with tarfile.open(PACKAGE / 'payload.tar.gz') as tf:
            names = tf.getnames()
            self.assertEqual(len(names), len(set(n.casefold() for n in names)), 'case-insensitive collision')
            for member in tf.getmembers():
                self.assertFalse(member.name.startswith('/') or '..' in Path(member.name).parts)
                self.assertNotIn('.git', Path(member.name).parts)
                self.assertFalse(member.name.endswith(('.zwc', '.pyc', '.zsh_history')))
                if member.issym():
                    self.assertFalse(member.linkname.startswith('/'))
            tf.extractall(self.home, filter='data')
        for p in self.home.rglob('*'):
            if p.is_symlink():
                self.assertTrue(p.resolve().is_relative_to(self.home) and p.exists(), str(p))
        self.assertFalse((self.home / '.oh-my-zsh/custom/kiro.zsh').exists())
        self.assertFalse((self.home / '.zsh_history').exists())
        self.assertFalse((self.home / '.local/share/zoxide').exists())

    def test_source_archive_excludes_history_and_personal_secrets(self):
        checked = 0
        with tarfile.open(PACKAGE / 'source-backup.tar.gz') as tf:
            for member in tf.getmembers():
                parts = Path(member.name).parts
                self.assertNotIn('.git', parts)
                self.assertNotIn('.zsh_history', parts)
                self.assertNotIn('.bash_history', parts)
                self.assertNotIn('db.zo', parts)
                if member.isfile() and (len(parts) == 1 or member.name == '.config/zsh_codex.ini'):
                    content = tf.extractfile(member).read().decode()
                    for line in content.splitlines():
                        m = re.match(r'^\s*(?:export\s+)?(\w*(?:API_KEY|api_key|TOKEN|PASSWORD|SECRET)\w*)\s*=\s*(.*)$', line)
                        if m:
                            self.assertTrue(not m[2] or m[2].startswith("''"), member.name + ': secret assignment not blank')
                            checked += 1
        self.assertGreaterEqual(checked, 2)

    def test_isolated_startup_without_optional_runtimes_or_ai(self):
        with tarfile.open(PACKAGE / 'payload.tar.gz') as tf:
            tf.extractall(self.home, filter='data')
        # A stub records any attempted curl/download; no real network requests allowed.
        bindir = self.base / 'bin'
        bindir.mkdir()
        for name in ['curl', 'wget']:
            p = bindir / name
            p.write_text('#!/bin/sh\nprintf attempted >> "$HOME/network-attempts"\nexit 99\n')
            p.chmod(0o700)
        git = bindir / 'git'
        git.write_text('#!/bin/sh\ncase "$*" in *clone*|*fetch*|*pull*) printf attempted >> "$HOME/network-attempts"; exit 99;; esac\nexec /usr/bin/git "$@"\n')
        git.chmod(0o700)
        self.env['PATH'] = str(bindir) + ':/usr/bin:/bin'
        self.env['XDG_DATA_HOME'] = str(self.home / 'custom-data')
        code = '''
            [[ $ZSH_THEME == robbyrussell ]] || exit 11
            for fn in _zsh_autosuggest_start _zsh_highlight history-substring-search-up zinit; do
                (( $+functions[$fn] )) || exit 12
            done
            (( ! $+functions[_zsh_ai_init_widget] )) || exit 13
            [[ ${_comps[git]} == _git && ${_comps[takar]} == _takar ]] || exit 14
            [[ ${ZINIT[HOME_DIR]} == "$HOME/.local/share/zinit" ]] || exit 15
            for annex in as-monitor bin-gem-node patch-dl rust; do
                name="zdharma-continuum/zinit-annex-$annex"
                (( ${ZINIT_REGISTERED_PLUGINS[(Ie)$name]} )) || exit 16
            done
            [[ $(alert 'notification-test') == notification-test ]] || exit 17
            print STARTUP_OK
        '''
        for mode in ['-ic', '-lic']:
            r = subprocess.run([ZSH, mode, code], env=self.env, cwd=self.home,
                               capture_output=True, text=True, timeout=45)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('STARTUP_OK', r.stdout)
            self.assertEqual(r.stderr, '')
        self.assertFalse((self.home / 'network-attempts').exists())

    def test_pty_widgets_and_local_ai_key_without_requests(self):
        # Test installed WSL executables against isolated configuration, never package them.
        fzf = Path.home() / '.fzf/bin/fzf'
        zoxide = Path.home() / '.local/bin/zoxide'
        if not fzf.exists() or not zoxide.exists():
            self.skipTest('WSL fzf/zoxide unavailable; Mac checks remain pending')
        with tarfile.open(PACKAGE / 'payload.tar.gz') as tf:
            tf.extractall(self.home, filter='data')
        bindir = self.base / 'bin'
        bindir.mkdir()
        (bindir / 'fzf').symlink_to(fzf)
        (bindir / 'zoxide').symlink_to(zoxide)
        for name in ['curl', 'wget']:
            p = bindir / name
            p.write_text('#!/bin/sh\nprintf attempted >> "$HOME/network-attempts"\nexit 99\n')
            p.chmod(0o700)
        self.env['PATH'] = str(bindir) + ':/usr/bin:/bin'
        (self.home / '.zsh-migration-secrets.zsh').write_text("export ZSH_AI_OPENAI_API_KEY='test-placeholder-not-a-credential'\n")
        master, slave = pty.openpty()
        code = '''
            [[ -o zle && -t 0 ]] || exit 21
            for widget in fzf-history-widget fzf-file-widget fzf-cd-widget history-substring-search-up; do
                (( $+widgets[$widget] )) || exit 22
            done
            (( $+functions[z] && $+functions[_zsh_ai_init_widget] )) || exit 23
            print PTY_OK
        '''
        try:
            proc = subprocess.Popen([ZSH, '-ic', code], env=self.env, cwd=self.home,
                                    stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = proc.communicate(timeout=45)
            self.assertEqual(proc.returncode, 0, stdout + stderr)
            self.assertIn('PTY_OK', stdout)
            self.assertEqual(stderr, '')
        finally:
            os.close(master)
            os.close(slave)
        self.assertFalse((self.home / 'network-attempts').exists())

    def test_public_linux_dry_run_makes_no_home_changes(self):
        if sys.platform != 'linux':
            self.skipTest('Linux/WSL test')
        r = subprocess.run([ZSH, '-f', str(PACKAGE / 'restore.zsh'), '--dry-run'],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('Dry run complete', r.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_public_restore_and_rollback_configuration_only(self):
        if os.geteuid() == 0:
            self.skipTest('Public installation intentionally refuses root')
        (self.home / '.zshrc').write_text('# original target shell\n')
        (self.home / '.zsh_history').write_text('preserve this\n')
        (self.home / '.zsh-migration-local.zsh').write_text('# local override\n')
        r = subprocess.run([ZSH, '-f', str(PACKAGE / 'restore.zsh'), '--skip-deps'],
                           env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        backups = list((self.home / '.zsh-migration-backups').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertTrue((self.home / '.oh-my-zsh/oh-my-zsh.sh').exists())
        r = subprocess.run([ZSH, '-f', str(PACKAGE / 'rollback.zsh'), str(backups[0])],
                           env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.home / '.zshrc').read_text(), '# original target shell\n')
        self.assertEqual((self.home / '.zsh_history').read_text(), 'preserve this\n')
        self.assertTrue((self.home / '.zsh-migration-local.zsh').exists())
        self.assertFalse((self.home / '.oh-my-zsh').exists())

    def test_older_distro_fzf_widgets(self):
        if not Path('/usr/share/doc/fzf/examples/key-bindings.zsh').exists():
            self.skipTest('Debian/Ubuntu fzf integration unavailable')
        with tarfile.open(PACKAGE / 'payload.tar.gz') as tf:
            tf.extractall(self.home, filter='data')
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([ZSH, '-ic', '(( $+widgets[fzf-history-widget] && $+widgets[fzf-file-widget] && $+widgets[fzf-cd-widget] ))'],
                                    env=self.env, cwd=self.home, stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = proc.communicate(timeout=45)
            self.assertEqual(proc.returncode, 0, stdout + stderr)
            self.assertEqual(stderr, '')
        finally:
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    unittest.main(verbosity=2)
