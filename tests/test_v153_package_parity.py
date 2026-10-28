"""V153 compiled IPA marker gate must match current host actual code."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
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
 b'[SCARLET_V151_TAB_NATIVE_PRESS] native_thumb=1\x00'
 b'[SCARLET_V151_ROW_PRESS] phase=pressed\x00'
 b'[SCARLET_V151_ORIENTATION_PARITY] host=\x00'
 b'[SCARLET_V151_FRAME_TOUCH_PARITY] host=\x00'
 b'[SCARLET_V151_CONTENT_STALE] host=\x00'
 b'[SCARLET_V153_RECENT_UNCLIPPED] press=native_glass\x00'
 b'[SCARLET_V153_DIRECT] host_anchor_visible=1\x00'
 b'[SCARLET_V153_DIRECT] route=host mode=direct picker=invoked')
BOOT=b'[SCARLET_V147_DIRECT] event=tap'

class V153CompiledParity(unittest.TestCase):
    def test_all_new_host_binary_signatures(self):
        verify_versioned_picker_markers('3.8.226',HOST,BOOT)
    def test_missing_v153_presses_and_route_rejected(self):
        for marker in (b'[SCARLET_V153_RECENT_UNCLIPPED] press=native_glass',
                       b'[SCARLET_V153_DIRECT] host_anchor_visible=1',
                       b'[SCARLET_V153_DIRECT] route=host mode=direct picker=invoked'):
            with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,"V153 compiled"):
                verify_versioned_picker_markers('3.8.226',HOST.replace(marker,b''),BOOT)
    def test_previous_version_binary_requirements_not_weakened(self):
        for marker in (b'[SCARLET_V151_ROW_PRESS] phase=pressed',
                       b'[SCARLET_V150_OUTSIDE] phase=touch_down'):
            with self.subTest(marker=marker),self.assertRaises(ValueError):
                verify_versioned_picker_markers('3.8.225',HOST.replace(marker,b''),BOOT)
    def test_source_contains_the_actual_new_literals(self):
        code=(ROOT/'scripts'/'patch_v153_three_fixes.py').read_text()
        for marker in ('[SCARLET_V153_RECENT_UNCLIPPED] press=native_glass',
                       '[SCARLET_V153_DIRECT] host_anchor_visible=1',
                       '[SCARLET_V153_DIRECT] route=host mode=direct picker=invoked'):
            self.assertIn(marker,code)
if __name__=="__main__":unittest.main()
