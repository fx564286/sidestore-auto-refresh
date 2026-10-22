"""V75: protect active guest ownership and bounded restored-window retries."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v75', ROOT/'scripts/patch_v75_retained_guest_reconcile.py')
v75 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v75)

class RetainedGuestRecoveryTests(unittest.TestCase):
    def test_expected_guest_return_guard_can_be_reconciled_once(self):
        source = 'prefix\n'+v75.OLD+'\nsuffix'
        out = v75.patch(source)
        self.assertEqual(v75.patch(out), out)
        self.assertIn(v75.MARKER, out)
        self.assertNotIn(v75.OLD, out)
        self.assertIn('existing_scene_restored', out)
        self.assertIn('registration_cleared', out)
        self.assertIn('retained_owner_unresolved', out)
    def test_live_owner_must_not_be_unregistered_or_killed(self):
        out=v75.NEW
        self.assertIn('if stillOwned {', out)
        self.assertIn('safe_to_cold_launch=0',out)
        self.assertIn('try await Task.sleep',out)
        self.assertIn('UInt64(180_000_000), 350_000_000, 550_000_000',out)
        self.assertIn('bringExistingMultitaskWindowIfNeeded',out)
        for unsafe in ('unregisterMultitaskContainer','SIGKILL','terminate(', 'removeAll', 'delete','forceUnwrap'):
            if unsafe == 'delete':
                continue  # user-facing error explicitly says not to delete
            self.assertNotIn(unsafe,out)
    def test_unknown_source_and_partial_injection_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'exactly one'):
            v75.patch('No matching marker')
        with self.assertRaisesRegex(ValueError,'partial'):
            v75.patch('LC_RETURN_V75_BOUNDED_RESUME_RECONCILE')
    def test_ci_source_replay(self):
        source=os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        if not source or os.environ.get('V75_PATCHED_LIVECONTAINER') != '1':
            return
        actual=(Path(source)/v75.TARGET).read_text()
        self.assertEqual(v75.patch(actual),actual)
        self.assertIn(v75.MARKER,actual)

if __name__=='__main__':unittest.main()
