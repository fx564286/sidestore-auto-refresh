"""V132: continuous finger-driven glass tracking and deterministic UI owner."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

v132=load("v132",ROOT/"scripts/patch_v132_glass_drag_one_owner.py")
v105=load("v105",ROOT/"scripts/patch_v105_delete_legacy_return.py")

class V132Tests(unittest.TestCase):
    def test_compose_against_previous_version(self):
        direct=v105.DIRECT_CODE
        native=v132.boot_patch(direct)
        self.assertEqual(v132.boot_patch(native),native)
        self.assertIn("nativeAvailableInForeground",native)
        self.assertIn("retireAllFallbacks:",native)
        self.assertEqual(native.count("SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc]"),1)
        self.assertEqual(native.count("nativeAvailableInForeground]"),3)
        self.assertIn("0.45*NSEC_PER_SEC",native)
        self.assertIn('fallback_created=1',native)
        self.assertIn('fallback_retired_all=1',native)
        for old in ('LCDirectReturnControl','LCReturnControl'):
            self.assertNotIn(old,native)
        self.assertNotIn('new UIWindow',native)

    def test_reference_glass_drag_source(self):
        src=(ROOT/"scripts/patch_v132_glass_drag_one_owner.py").read_text()
        for token in ("UISelectionFeedbackGenerator", "rim.followFinger(fraction)",
                      "minimumNumberOfTouches", "glassPan.cancelsTouchesInView = false",
                      "picker.sendActions(for: .valueChanged)", "SCNativeGlassFingerTracker",
                      "UIPanGestureRecognizer", "isEnabledForSegment(at: index)",
                      "SCARLET_V132_ONE_HANDLE"):
            with self.subTest(token=token):
                self.assertIn(token,src)
        self.assertNotIn("UIWindow(frame:",src)
        self.assertNotIn("SecItemDelete",src)

    def test_generated_final_sources(self):
        root=os.environ.get("V132_PATCHED_LIVECONTAINER")
        if not root: return
        root=Path(root)
        swift=(root/v132.DOCK).read_text()
        objc=(root/v132.BOOT).read_text()
        self.assertEqual(v132.dock_patch(swift),swift)
        self.assertEqual(v132.boot_patch(objc),objc)
        self.assertEqual(swift.count("private final class SCNativeGlassFingerTracker"),1)
        self.assertEqual(swift.count("UIPanGestureRecognizer(target: glassTracking"),1)
        self.assertEqual(swift.count("tabPicker.addAction("),1)
        self.assertEqual(swift.count("item.configuration = .plain()"),3)
        self.assertEqual(swift.count("UIGlassEffect(style: .clear)"),1)
        self.assertEqual(swift.count("picker.sendActions(for: .valueChanged)"),1)
        self.assertEqual(objc.count("SCGuestMorphWindow *window = [[SCGuestMorphWindow alloc]"),1)
        self.assertIn("retireAllFallbacks",objc)
        self.assertIn("nativeAvailableInForeground",objc)

if __name__=="__main__":unittest.main()
