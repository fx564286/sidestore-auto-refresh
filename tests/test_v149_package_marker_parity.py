"""V149 package/compiled marker parity: prevent stale V147 outside-tap gates.

The V149 UI source removed V147's one-time monitor log intentionally.
Tests fail at the start of CI when packager asks for a removed literal.
"""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from package_livecontainer_combined import verify_versioned_picker_markers

COMMON=(
    b'[SCARLET_V147_GLASS] panel=clear tabs=native rows=native\x00'
    b'[SCARLET_V147_DIRECT] route=host result=presented\x00'
    b'[SCARLET_V147_ACTION_GLASS] button='
)
BOOT=b'[SCARLET_V147_DIRECT] event=tap'

class VersionedPickerMarkers(unittest.TestCase):
    def test_v147_v148_keep_original_outside_observer(self):
        v147=COMMON+b'\x00[SCARLET_V147_OUTSIDE] monitors='
        verify_versioned_picker_markers('3.8.220',v147,BOOT)
        with self.assertRaisesRegex(ValueError,'original outside observer'):
            verify_versioned_picker_markers('3.8.220',COMMON,BOOT)
        v148=v147+b'\x00[SCARLET_V148_ACTION_GLASS] action='
        verify_versioned_picker_markers('3.8.221',v148,BOOT)
        with self.assertRaisesRegex(ValueError,'V148 compiled native'):
            verify_versioned_picker_markers('3.8.221',v147,BOOT)

    def test_v149_requires_actual_current_glass_and_dynamic_observer(self):
        host=COMMON+(
            b'\x00[SCARLET_V148_ACTION_GLASS] action='
            b'\x00[SCARLET_V149_TABS] style=system_native'
            b'\x00[SCARLET_V149_ACTION_GLASS] action='
            b'\x00[SCARLET_V149_OUTSIDE] monitor_attached'
            b'\x00[SCARLET_V149_OUTSIDE] scene_monitor_count='
        )
        verify_versioned_picker_markers('3.8.222',host,BOOT)
        for marker in (b'[SCARLET_V149_TABS] style=system_native',
                       b'[SCARLET_V149_ACTION_GLASS] action=',
                       b'[SCARLET_V149_OUTSIDE] monitor_attached',
                       b'[SCARLET_V149_OUTSIDE] scene_monitor_count='):
            with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,'V149 compiled picker'):
                verify_versioned_picker_markers('3.8.222',host.replace(marker,b''),BOOT)
        with self.assertRaisesRegex(ValueError,'Direct button'):
            verify_versioned_picker_markers('3.8.222',host,b'')

    def test_expected_v149_markers_are_in_patched_real_ui_source(self):
        # This is the source used by the actual V149 patch, not a fake UI path.
        doc=(ROOT/"scripts"/"patch_v149_controls.py").read_text()
        self.assertIn('[SCARLET_V149_TABS] style=system_native',doc)
        self.assertIn('[SCARLET_V149_OUTSIDE] scene_monitor_count=',doc)
        self.assertIn('[SCARLET_V149_OUTSIDE] monitor_attached',doc)
        self.assertNotIn('[SCARLET_V147_OUTSIDE] monitors=',doc)

    def test_v149_does_not_depend_on_deleted_v147_monitor(self):
        import inspect
        source=inspect.getsource(verify_versioned_picker_markers)
        self.assertIn("version in ('3.8.220', '3.8.221')",source)
        self.assertNotIn("version in ('3.8.220', '3.8.221', '3.8.222'):\n        if b'[SCARLET_V147_OUTSIDE]",source)

if __name__=="__main__":
    unittest.main()
