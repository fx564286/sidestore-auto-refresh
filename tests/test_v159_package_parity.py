"""V159 compiled marker gate for fixed frame and native-only glass press."""
import unittest
from tests.test_v158_package_parity import BOOT
from scripts.package_livecontainer_combined import verify_versioned_picker_markers

BASE=(
    b'[SCARLET_V144_GLASS_INSTALLED]\x00'
    b'[SCARLET_V149_TABS] style=system_native\x00'
    b'[SCARLET_V149_ACTION_GLASS] action=\x00'
    b'[SCARLET_V150_OUTSIDE] phase=touch_down\x00'
    b'[SCARLET_V154_OUTSIDE] stage=backdrop_touch\x00'
    b'[SCARLET_V155_SINGLE] stage=guest_launch route=LiveProcess\x00'
    b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=backdrop_received\x00'
    b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=window_should_receive\x00'
    b'[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_completed\x00'
    b'[SCARLET_V157_WIDTH] viewport=\x00'
    b'[SCARLET_V158_FRAME_HEIGHT] list_height=\x00'
    b'[SCARLET_V158_ACTION_UNCLIPPED] actions=\x00'
)
CURRENT=(b'[SCARLET_V159_PANEL_EQUAL] height=',
         b'[SCARLET_V159_ACTION_NATIVE_PRESS] phase=began')
class CompiledV159(unittest.TestCase):
    def test_full_binary_contract(self):
        verify_versioned_picker_markers('3.8.232',BASE+b'\x00'.join(CURRENT),BOOT)
    def test_new_behavior_mandatory(self):
        for i,marker in enumerate(CURRENT):
            with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,'V159 compiled'):
                verify_versioned_picker_markers('3.8.232',BASE+b'\x00'.join(CURRENT[:i]+CURRENT[i+1:]),BOOT)
    def test_deleted_direct_remains_forbidden(self):
        with self.assertRaisesRegex(ValueError,'Direct'):
            verify_versioned_picker_markers('3.8.232',BASE+b'\x00'.join(CURRENT),BOOT+b'SCGuestMorphPresenter')
if __name__=="__main__":unittest.main()
