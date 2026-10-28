"""V151 package parity keeps V150 touch and verifies native geometry binary."""
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from package_livecontainer_combined import verify_versioned_picker_markers

HOST=(b'[SCARLET_V147_GLASS] panel=clear tabs=native rows=native\x00'
 b'[SCARLET_V147_DIRECT] route=host result=presented\x00'
 b'[SCARLET_V147_ACTION_GLASS] button=\x00'
 b'[SCARLET_V148_ACTION_GLASS] action=\x00'
 b'[SCARLET_V149_TABS] style=system_native\x00'
 b'[SCARLET_V149_ACTION_GLASS] action=\x00'
 b'[SCARLET_V149_OUTSIDE] scene_monitor_count=\x00'
 b'[SCARLET_V150_LONG_PRESS] phase=bulge\x00'
 b'[SCARLET_V150_LONG_PRESS] phase=release\x00'
 b'[SCARLET_V150_OUTSIDE] phase=touch_down\x00'
 b'[SCARLET_V150_TABS_UNIFIED] tint=translucent\x00'
 b'[SCARLET_V151_ORIENTATION_PARITY] host=\x00'
 b'[SCARLET_V151_FRAME_TOUCH_PARITY] host=\x00'
 b'[SCARLET_V151_CONTENT_STALE] host=\x00'
 b'[SCARLET_V151_TAB_NATIVE_PRESS] native_thumb=1\x00'
 b'[SCARLET_V151_ROW_PRESS] phase=pressed')
BOOT=b'[SCARLET_V147_DIRECT] event=tap'

class V151PackageParity(unittest.TestCase):
    def test_current_geometry_and_all_prior_controls(self):
        verify_versioned_picker_markers('3.8.224',HOST,BOOT)

    def test_missing_geometry_marker_fails(self):
        for marker in (b'[SCARLET_V151_ORIENTATION_PARITY] host=',
                       b'[SCARLET_V151_FRAME_TOUCH_PARITY] host=',
                       b'[SCARLET_V151_CONTENT_STALE] host='):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError,"V151 compiled"):
                verify_versioned_picker_markers('3.8.224',HOST.replace(marker,b''),BOOT)

    def test_missing_capsule_and_native_press_markers_fail(self):
        for marker in (b'[SCARLET_V151_TAB_NATIVE_PRESS] native_thumb=1',
                       b'[SCARLET_V151_ROW_PRESS] phase=pressed'):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, "V151 compiled"):
                verify_versioned_picker_markers('3.8.224',HOST.replace(marker,b''),BOOT)

    def test_existing_long_press_and_outside_touch_remain_required(self):
        for marker in (b'[SCARLET_V150_LONG_PRESS] phase=bulge',
                       b'[SCARLET_V150_OUTSIDE] phase=touch_down'):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError,"V150 compiled"):
                verify_versioned_picker_markers('3.8.224',HOST.replace(marker,b''),BOOT)

if __name__=="__main__": unittest.main()
