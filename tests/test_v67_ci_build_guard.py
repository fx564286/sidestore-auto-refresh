"""Verify the Xcode CI watchdog records diagnostics and exits on a hang."""
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_bounded_build import run, tail


class CIBuildWatchdogTests(unittest.TestCase):
    def test_success_retains_full_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'success.log'
            self.assertEqual(0, run([sys.executable, '-c', 'print("V67_READY")'], log, 10))
            self.assertIn('V67_READY', log.read_text())

    def test_failure_captures_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'error.log'
            self.assertEqual(7, run([sys.executable, '-c',
                                     'print("SENTINEL_ERROR", flush=True);raise SystemExit(7)'], log, 10))
            self.assertIn('SENTINEL_ERROR', tail(log))

    def test_bounded_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'timeout.log'
            self.assertEqual(124, run([sys.executable, '-c',
                                       'import time;print("STARTED",flush=True);time.sleep(9)'], log, 1))
            self.assertIn('STARTED', log.read_text())


if __name__ == '__main__':
    unittest.main()
