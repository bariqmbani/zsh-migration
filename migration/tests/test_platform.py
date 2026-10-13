#!/usr/bin/env python3
"""Exercise platform/package dispatch without installing packages or spoofing a host."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]
ZSH = shutil.which('zsh')


class PlatformTests(unittest.TestCase):
    def shell(self, code, env=None):
        base_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home()), 'KIT': str(KIT)}
        if env:
            base_env.update(env)
        return subprocess.run([ZSH, '-fc', 'source "$KIT/lib/platform.zsh"\n' + code],
                              env=base_env, capture_output=True, text=True, timeout=20)

    def test_platform_detection(self):
        cases = [('Linux', '6.8.0-generic', '', 'linux'),
                 ('Linux', '5.15-microsoft-standard-WSL2', '', 'wsl'),
                 ('Linux', '6.1-custom', 'Ubuntu', 'wsl'),
                 ('Darwin', '25.0', '', 'macos'),
                 ('FreeBSD', '14.0', '', 'freebsd'),
                 ('OpenBSD', '7.7', '', 'openbsd'),
                 ('NetBSD', '10.0', '', 'netbsd'),
                 ('DragonFly', '6.4', '', 'dragonfly')]
        for kernel, release, distro, expected in cases:
            with self.subTest(kernel=kernel, release=release):
                r = self.shell('migration_classify_platform "$KERNEL" "$RELEASE" "$DISTRO" || exit; print -r -- "$MIGRATION_PLATFORM"',
                               {'KERNEL': kernel, 'RELEASE': release, 'DISTRO': distro})
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), expected)

    def test_native_windows_is_rejected(self):
        r = self.shell('migration_classify_platform Windows_NT 10 ""')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('requires WSL', r.stderr)

    def test_package_command_arguments(self):
        expected = {
            'apt-get': 'sudo apt-get install -y git curl',
            'dnf': 'sudo dnf install -y git curl',
            'pacman': 'sudo pacman -S --needed git curl',
            'zypper': 'sudo zypper --non-interactive install git curl',
            'apk': 'sudo apk add git curl',
            'brew': 'brew install git curl',
        }
        for manager, command in expected.items():
            with self.subTest(manager=manager):
                r = self.shell('migration_package_command "$MANAGER" git curl; print -r -- "${MIGRATION_INSTALL_COMMAND[*]}"',
                               {'MANAGER': manager})
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), command)

    def test_unknown_package_manager_fails_cleanly(self):
        r = self.shell('migration_package_command manual git')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('--skip-deps', r.stderr)

    def test_failed_dependency_install_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            sudo = Path(tmp) / 'sudo'
            sudo.write_text('#!/bin/sh\nexit 42\n')
            sudo.chmod(0o700)
            r = self.shell('''
                MIGRATION_PLATFORM=linux
                MIGRATION_MANAGER=dnf
                migration_missing_dependencies() { MIGRATION_MISSING=(git); }
                migration_install_dependencies /tmp
            ''', {'PATH': tmp + ':/usr/bin:/bin'})
            self.assertNotEqual(r.returncode, 0)

    def test_linux_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.shell('''
                source "$KIT/templates/environment.zsh"
                [[ $ANDROID_HOME == "$HOME/Android/Sdk" ]] || exit 1
                [[ -z ${GOROOT:-} ]] || exit 2
                print PASS
            ''', {'HOME': tmp, 'GOROOT': '/nonexistent/source-go'})
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
