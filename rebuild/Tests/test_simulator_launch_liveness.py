"""Regression: a simctl launch receipt is not proof of a surviving app."""
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'diagnostics/scarlet_ios_simulator_smoke.py'
SPEC = importlib.util.spec_from_file_location('scarlet_smoke_liveness', SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class SimulatorLaunchLiveness(unittest.TestCase):
    def scenario(self, snapshots, receipt='test.scarlet.smoke: 123'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / 'LiveContainer.app'
            app.mkdir()
            (app / 'Info.plist').write_bytes(plistlib.dumps(
                {'CFBundleIdentifier': 'test.scarlet.smoke'}))
            probes = iter(snapshots)
            calls = []

            def fake_run(args, *, stage, timeout=100, cwd=None):
                calls.append(args)
                if args[:4] == ['xcrun', 'simctl', 'list', '-j']:
                    return json.dumps({'devices': {
                        'com.apple.CoreSimulator.SimRuntime.iOS-27-2': [
                            {'name': 'iPhone 18 Pro', 'udid': 'test-id', 'state': 'Booted'}]}})
                if args[:3] == ['xcrun', 'simctl', 'launch']:
                    return receipt
                if args[:3] == ['xcrun', 'simctl', 'spawn']:
                    return next(probes)
                if args[:3] == ['xcrun', 'simctl', 'io']:
                    Path(args[-1]).write_bytes(b'fake screenshot' * 100)
                return ''

            with patch.object(smoke, 'simulator_build', return_value=app), \
                 patch.object(smoke, 'run', side_effect=fake_run), \
                 patch.object(smoke.time, 'sleep'), \
                 patch('sys.argv', ['smoke', '--engine', str(root), '--report-dir', str(root/'report')]):
                status = smoke.main()
            return status, json.loads((root/'report/smoke.json').read_text()), calls

    live = 'PID\tStatus\tLabel\n123\t0\tUIKitApplication:test.scarlet.smoke[abc][rb-legacy]'
    dead = 'PID\tStatus\tLabel\n-\t9\tUIKitApplication:test.scarlet.smoke[abc][rb-legacy]'

    def test_exit_before_capture_is_blocked(self):
        rc, report, calls = self.scenario([self.dead])
        self.assertEqual(rc, 2)
        self.assertEqual(report['stage'], 'simulator_launch_liveness_failed')
        self.assertFalse(any(c[:3] == ['xcrun', 'simctl', 'io'] for c in calls))

    def test_exit_during_capture_is_blocked(self):
        rc, report, _ = self.scenario([self.live, self.dead])
        self.assertEqual(rc, 2)
        self.assertEqual(report['result'], 'blocked')

    def test_pid_reuse_by_different_bundle_is_blocked(self):
        rc, _, _ = self.scenario([self.live.replace('test.scarlet.smoke', 'test.scarlet.smoke.other')])
        self.assertEqual(rc, 2)

    def test_wrong_launch_receipt_is_blocked(self):
        rc, _, _ = self.scenario([], receipt='other.bundle: 123')
        self.assertEqual(rc, 2)

    def test_surviving_same_process_has_two_probes(self):
        rc, report, calls = self.scenario([self.live, self.live])
        self.assertEqual(rc, 0)
        self.assertEqual(report['launch_liveness'], 'verified_before_and_after_screenshot')
        self.assertEqual(sum(c[:3] == ['xcrun', 'simctl', 'spawn'] for c in calls), 2)


if __name__ == '__main__':
    unittest.main()
