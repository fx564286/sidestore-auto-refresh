"""V156 binary marker regression: proves new compiled code, not device interaction."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from package_livecontainer_combined import verify_versioned_picker_markers

COMMON=(
 b'[SCARLET_V144_GLASS_INSTALLED]\x00'
 b'[SCARLET_V149_TABS] style=system_native\x00'
 b'[SCARLET_V149_ACTION_GLASS] action=\x00'
 b'[SCARLET_V150_OUTSIDE] phase=touch_down\x00'
 b'[SCARLET_V154_OUTSIDE] stage=backdrop_touch\x00'
 b'[SCARLET_V155_SINGLE] stage=guest_launch route=LiveProcess\x00'
)
CURRENT=(
 b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=backdrop_received\x00',
 b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=window_should_receive\x00',
 b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_completed\x00',
)
BOOT=b'[SCARLET_V155_SINGLE] stage=bootstrap result=direct_rejected\x00'

class V156Binary(unittest.TestCase):
    def test_current_markers(self):
        verify_versioned_picker_markers('3.8.229',COMMON+b''.join(CURRENT),BOOT)
    def test_missing_each_current_marker_rejected(self):
        host=COMMON+b''.join(CURRENT)
        for marker in CURRENT:
            with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,'V156 compiled'):
                verify_versioned_picker_markers('3.8.229',host.replace(marker,b''),BOOT)
    def test_legacy_direct_cannot_return(self):
        for bad in (b'SCGuestMorphPresenter',
                    b'scarletcrystal251://nrg-guest-controls',
                    b'[SCARLET_V154_DIRECT_TAP_RECOGNIZER]'):
            with self.subTest(old=bad),self.assertRaisesRegex(ValueError,'retired Direct'):
                verify_versioned_picker_markers('3.8.229',COMMON+b''.join(CURRENT),BOOT+bad)

if __name__=="__main__":unittest.main()
