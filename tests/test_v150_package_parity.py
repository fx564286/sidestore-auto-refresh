"""V150 compiled IPA marker parity, without weakening prior release gates."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from package_livecontainer_combined import verify_versioned_picker_markers

OLD = (b'[SCARLET_V147_GLASS] panel=clear tabs=native rows=native\x00'
       b'[SCARLET_V147_DIRECT] route=host result=presented\x00'
       b'[SCARLET_V147_ACTION_GLASS] button=\x00'
       b'[SCARLET_V148_ACTION_GLASS] action=\x00')
BOOT=b'[SCARLET_V147_DIRECT] event=tap'
CURRENT = (OLD +
    b'[SCARLET_V149_TABS] style=system_native\x00'
    b'[SCARLET_V149_ACTION_GLASS] action=\x00'
    b'[SCARLET_V149_OUTSIDE] scene_monitor_count=\x00'
    b'[SCARLET_V150_LONG_PRESS] phase=bulge\x00'
    b'[SCARLET_V150_LONG_PRESS] phase=release\x00'
    b'[SCARLET_V150_OUTSIDE] phase=touch_down\x00'
    b'[SCARLET_V150_TABS_UNIFIED] tint=translucent\x00')

class V150BinaryMarkers(unittest.TestCase):
    def test_current_binary_contract(self):
        verify_versioned_picker_markers('3.8.223',CURRENT,BOOT)

    def test_missing_current_interactive_marker_fails(self):
        for marker in (b'[SCARLET_V150_LONG_PRESS] phase=bulge',
                       b'[SCARLET_V150_LONG_PRESS] phase=release',
                       b'[SCARLET_V150_OUTSIDE] phase=touch_down',
                       b'[SCARLET_V150_TABS_UNIFIED] tint=translucent'):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError,'V150 compiled'):
                verify_versioned_picker_markers('3.8.223',
                                                CURRENT.replace(marker,b''),BOOT)

    def test_replaced_v149_attachment_marker_is_not_required(self):
        self.assertNotIn(b'[SCARLET_V149_OUTSIDE] monitor_attached',CURRENT)
        verify_versioned_picker_markers('3.8.223',CURRENT,BOOT)

    def test_old_versions_still_require_their_original_observer(self):
        old=b'[SCARLET_V147_GLASS] panel=clear tabs=native rows=native\x00'
        old+=b'[SCARLET_V147_DIRECT] route=host result=presented\x00'
        old+=b'[SCARLET_V147_ACTION_GLASS] button='
        with self.assertRaisesRegex(ValueError,'original outside observer'):
            verify_versioned_picker_markers('3.8.220',old,BOOT)

    def test_generated_runtime_source_has_every_new_literal(self):
        src=Path(ROOT/'scripts/patch_v150_touch_glass.py').read_text()
        for marker in (b'[SCARLET_V150_LONG_PRESS] phase=bulge',
                       b'[SCARLET_V150_OUTSIDE] phase=touch_down',
                       b'[SCARLET_V150_TABS_UNIFIED] tint=translucent'):
            self.assertIn(marker.decode(),src)

if __name__=="__main__":unittest.main()
