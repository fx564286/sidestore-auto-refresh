"""Compiled V157 binary must carry wider-screen geometry marker.

This does not claim iPhone visual acceptance; it rejects a stale built IPA.
"""
import unittest
from tests.test_v156_package_parity import COMMON, CURRENT, BOOT
from scripts.package_livecontainer_combined import verify_versioned_picker_markers

WIDTH=b'[SCARLET_V157_WIDTH] viewport='
BASE=COMMON+b''.join(CURRENT)

class V157CompiledPanel(unittest.TestCase):
    def test_wide_panel_compiled(self):
        verify_versioned_picker_markers('3.8.230',BASE+WIDTH,BOOT)
    def test_wide_panel_missing_rejected(self):
        with self.assertRaisesRegex(ValueError,'V157 compiled'):
            verify_versioned_picker_markers('3.8.230',BASE,BOOT)
    def test_outside_trace_and_direct_removal_still_required(self):
        with self.assertRaises(ValueError):
            verify_versioned_picker_markers('3.8.230',
                BASE.replace(b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_completed',b'')+WIDTH,BOOT)
        with self.assertRaisesRegex(ValueError,'Direct'):
            verify_versioned_picker_markers('3.8.230',BASE+WIDTH,BOOT+b'SCGuestMorphPresenter')

if __name__=="__main__":unittest.main()
