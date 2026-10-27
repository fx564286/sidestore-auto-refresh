"""V133: prevent keyboard stuck under picker and across virtual guest handoff."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v133",ROOT/"scripts/patch_v133_keyboard_focus_handoff.py")
v133=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v133)


class KeyboardHandoff(unittest.TestCase):
    def test_no_process_wide_resign_or_guest_view_resize(self):
        source=(ROOT/"scripts/patch_v133_keyboard_focus_handoff.py").read_text()
        for banned in ("UIApplication.shared.sendAction(", "UIKeyboardFrameEndUserInfoKey",
                       "setTranslation:CGPointZero", "keyboardWindow.hidden", "UIWindow(frame:",
                       "SecItemDelete(", "CADisplayLink", "UIResponder.resignFirstResponder"):
            self.assertNotIn(banned,source)
        self.assertIn("keyboardOwner.endEditing(true)",source)
        self.assertIn("keyboardOwner.windowLevel == .normal",source)
        self.assertIn("candidate.isKeyWindow",source)
        self.assertIn("candidate.windowLevel == .normal",source)
        self.assertIn("hadGuestResponder && self.view.window != nil",source)
        self.assertIn("nrgV133ContainsActiveResponder",source)

    def test_precondition_fails_closed(self):
        with self.assertRaises(ValueError):
            v133.dock_patch("unrelated")
        with self.assertRaises(ValueError):
            v133.dec_patch("unrelated")

    def test_patched_generated_sources(self):
        root=os.environ.get("V133_PATCHED_LIVECONTAINER")
        if not root:return
        root=Path(root)
        dock=(root/v133.DOCK).read_text()
        dec=(root/v133.DEC).read_text()
        self.assertEqual(v133.dock_patch(dock),dock)
        self.assertEqual(v133.dec_patch(dec),dec)
        self.assertEqual(dock.count(v133.MARK),1)
        self.assertEqual(dec.count(v133.MIN),1)
        self.assertEqual(dock.count("keyboardOwner.endEditing(true)"),1)
        self.assertEqual(dock.count("private func prepareKeyboardForGuestSwitch"),1)
        self.assertIn("SCARLET_V132_GLASS_DRAG",dock)
        self.assertIn("SCARLET_V129_PICKER_RESILIENCE",dock)
        self.assertIn("NRG_V46_MINIMIZE_KEYBOARD_SCOPE",dec)
        self.assertIn("if (hadGuestResponder && self.view.window != nil)",dec)
        self.assertNotIn("UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder)",dock)

if __name__=="__main__":unittest.main()
