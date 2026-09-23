import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('initializer', ROOT / 'scripts/init-notebook.py')
initializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(initializer)


class SetupTests(unittest.TestCase):
    def test_private_initialization_and_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'private notebook'
            initializer.initialize(target)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertTrue((target / 'AGENTS.md').exists())
            self.assertEqual(subprocess.check_output(['git', '-C', str(target), 'remote']), b'')
            self.assertNotIn('Example food', (target / 'meal-log.org').read_text())
            sentinel = target / 'private-record'
            sentinel.write_text('preserve')
            with self.assertRaises(ValueError):
                initializer.initialize(target)
            self.assertEqual(sentinel.read_text(), 'preserve')

    def test_public_checkout_and_symlink_rejected(self):
        with self.assertRaises(ValueError):
            initializer.initialize(ROOT / 'accidental-records')
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / 'link'
            link.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaises(ValueError):
                initializer.initialize(link / 'accidental-records')
            dangling = Path(tmp) / 'dangling'
            dangling.symlink_to(Path(tmp) / 'missing')
            with self.assertRaises(ValueError):
                initializer.initialize(dangling)

    def run_launcher(self, resume_exit, mode):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / 'health-notebook').mkdir()
            binary = home / '.local/bin/claude'
            binary.parent.mkdir(parents=True)
            binary.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$HOME/calls"\n'
                              'if [[ "$*" == *--continue* ]]; then exit "${RESUME_EXIT}"; fi\n')
            binary.chmod(0o755)
            env = dict(os.environ, HOME=tmp, RESUME_EXIT=str(resume_exit),
                       HEALTH_NOTEBOOK_PERMISSION_MODE=mode)
            result = subprocess.run(['bash', str(ROOT / 'scripts/health-notebook-remote.sh')],
                                    env=env, capture_output=True)
            calls = (home / 'calls').read_text().splitlines() if (home / 'calls').exists() else []
            return result.returncode, calls

    def test_resume_and_fallback(self):
        code, calls = self.run_launcher(0, 'acceptEdits')
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        code, calls = self.run_launcher(1, 'default')
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2)
        self.assertIn('--capacity 1', calls[1])
        self.assertTrue(all('--permission-mode default' in call for call in calls))
        self.assertTrue(all('bypassPermissions' not in call for call in calls))

    def test_invalid_mode_never_launches(self):
        code, calls = self.run_launcher(0, 'unexpected')
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
