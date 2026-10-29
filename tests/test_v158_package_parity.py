"""V158 compiled markers: panel height and action optical clearance preserved.

These assert binary inclusion, not real device pixel-perfect behavior.
"""
import unittest
try:
    from tests.test_v157_package_parity import BASE, BOOT, WIDTH
except ModuleNotFoundError as e:
    if e.name != "tests": raise
    from test_v157_package_parity import BASE, BOOT, WIDTH
import sys
from pathlib import Path

# unittest discovery from a parent directory does not add builder/ to sys.path.
# Match V156 and earlier marker tests without weakening the import gate.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from package_livecontainer_combined import verify_versioned_picker_markers

EQUAL=b'[SCARLET_V158_FRAME_HEIGHT] list_height='
ACTIONS=b'[SCARLET_V158_ACTION_UNCLIPPED] actions='

class V158BinaryMarkers(unittest.TestCase):
    def test_both_modes_share_frame_and_actions_do_not_clip(self):
        verify_versioned_picker_markers('3.8.231',BASE+WIDTH+EQUAL+ACTIONS,BOOT)
    def test_missing_each_marker_fails(self):
        for bad in (EQUAL,ACTIONS):
            with self.subTest(marker=bad), self.assertRaisesRegex(ValueError,"V158 compiled"):
                verify_versioned_picker_markers('3.8.231',
                   (BASE+WIDTH+EQUAL+ACTIONS).replace(bad,b''), BOOT)
    def test_retired_direct_paths_remain_disallowed(self):
        with self.assertRaises(ValueError):
            verify_versioned_picker_markers('3.8.231',
                BASE+WIDTH+EQUAL+ACTIONS,BOOT+b'SCGuestMorphPresenter')

if __name__=="__main__":unittest.main()
