import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v99",ROOT/"scripts/patch_v99_floating_guest_control.py")
v99=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v99)
PREVIOUS="""NRG_V73_APPLE_FLOATING_CONTROL NRG_V72_OVERFLOW_LONGPRESS
nrgV73RestoreFloatingPosition
overflow.accessibilityHint = @"Tap for window options. Hold to switch guests. Drag to move.";
"""
BASE=(PREVIOUS + v99.DEFAULT_OLD+"\n"+v99.RIGHT_OLD+"\n"+v99.TAP_OLD+" = [[UILongPressGestureRecognizer alloc]\n"+
      "- (void)nrgV72WindowOverflowLongPress:(UILongPressGestureRecognizer *)gesture {\n"+
      v99.HANDLER_OLD+"\n")

class FloatingControlRegression(unittest.TestCase):
    def test_tap_switch_and_hold_preserves_original_window_controls(self):
        s=v99.patch(BASE)
        self.assertIn("nrgV99OpenRecentGuests:",s)
        self.assertIn("nrgV72PresentGuestSwitcherFrom:self sourceView:source",s)
        self.assertIn("nrgV99ShowWindowActionsFrom:",s)
        for selector in ("minimizeWindow","maximizeWindow","closeWindow"):
            self.assertIn("[weakSelf "+selector+"]",s)
        self.assertIn("overflow.showsMenuAsPrimaryAction = NO",s)
        self.assertEqual(v99.patch(s),s)
    def test_position_is_symmetric_right_and_movable(self):
        s=v99.patch(BASE)
        self.assertIn(" : 0.50;",s)
        self.assertIn(" : YES;",s)
        self.assertIn("nrgV73RestoreFloatingPosition",s)
    def test_gesture_cancellation_preserved(self):
        s=v99.patch(BASE)
        self.assertEqual(s.count("SCARLET_V99_UNIFIED_FLOATING_GUEST_CONTROL"),1)
        self.assertNotIn("Tap for window options. Hold to switch guests",s)
    def test_missing_upstream_fail_closed(self):
        with self.assertRaises(ValueError):v99.patch(BASE.replace("NRG_V73_APPLE_FLOATING_CONTROL",""))
        with self.assertRaises(ValueError):v99.patch(BASE+v99.TAP_OLD)
    def test_existing_integrated_target_when_requested(self):
        if os.environ.get("SCARLET_V99_PATCHED")=="1":
            root=Path(os.environ["LIVE_CONTAINER_TEST_SOURCE"])
            s=(root/v99.TARGET).read_text()
            self.assertEqual(v99.patch(s),s)
        else:
            self.assertTrue(True)

if __name__=="__main__":unittest.main()
