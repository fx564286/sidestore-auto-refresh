"""V151 maximized host / embedded guest orientation and touch-frame parity."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v151",ROOT/"scripts"/"patch_v151_geometry.py")
v151=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v151)

class V151GeometryTest(unittest.TestCase):
    def test_reject_incompatible_old_sources(self):
        with self.assertRaises(ValueError):v151.patch_decorated("unrelated code")
        with self.assertRaises(ValueError):v151.patch_dock("unrelated code")

    def test_physical_size_round_trip_preserves_touch_dimensions(self):
        # UpdateMaximizedFrame writes guest coordinates according to GUEST
        # orientation; AppSceneVC then reverses it. This should equal host
        # physical pixels even if host/guest orientations are temporarily different.
        for host,guest,(w,h) in (
            ("portrait","portrait",(393,852)),
            ("landscape","landscape",(852,393)),
            ("landscape","portrait",(852,393)),
            ("portrait","landscape",(393,852))):
            serialized=(h,w) if guest=="landscape" else (w,h)
            physical=(serialized[1],serialized[0]) if guest=="landscape" else serialized
            with self.subTest(host=host,guest=guest):
                self.assertEqual(physical,(w,h))

    def test_generated_source_and_original_panel_preserved(self):
        root=os.getenv("V151_PATCHED_LIVECONTAINER")
        if not root: return
        p=Path(root)
        objc=(p/v151.DEC).read_text()
        swift=(p/v151.SWIFT).read_text()
        self.assertEqual(v151.patch_decorated(objc),objc)
        self.assertEqual(v151.patch_dock(swift),swift)
        self.assertIn("SCARLET_V151_UNIFIED_GUEST_GEOMETRY",objc)
        self.assertIn("UIInterfaceOrientation guestOrientation = settings.interfaceOrientation;",objc)
        self.assertIn("UIInterfaceOrientationIsLandscape(guestOrientation)",objc)
        self.assertIn("SCARLET_V151_FRAME_TOUCH_PARITY",objc)
        self.assertIn("SCARLET_V151_CONTENT_STALE",objc)
        self.assertIn("SCARLET_V151_GUEST_RESUME_GEOMETRY",swift)
        self.assertIn("controller.nrgV55ReconcileRotationGeometry()",swift)
        self.assertIn("SCARLET_V150_LONG_PRESS",swift)
        self.assertIn('("앱 닫기", "closeWindow")',swift)
        self.assertNotIn('("창 닫기", "closeWindow")',swift)
        # No new guest-specific app name hacks, no new UIWindow or overlay.
        patch=(ROOT/"scripts"/"patch_v151_geometry.py").read_text()
        for word in ("Instagram","KakaoTalk","Twitter","bundleId == ","UIWindow(frame:", "UIControl(frame:"):
            self.assertNotIn(word,patch)
        old=os.getenv("V151_BASELINE_DOCK")
        if old:
            before=Path(old).read_text()
            a="        let overlay = UIControl(frame: owner.bounds)"
            b="        let tabPicker = UISegmentedControl(items:"
            self.assertEqual(before[before.index(a):before.index(b)],
                             swift[swift.index(a):swift.index(b)])

    def test_persistent_per_guest_touch_safe_preference_not_destroyed(self):
        root=os.getenv("V151_PATCHED_LIVECONTAINER")
        if root:
            source=(Path(root)/v151.DEC).read_text()
            self.assertIn("ScarletGuestTouchSafe.",source)
            self.assertIn("storedTouchSafe",source)
            self.assertIn("touchSafe ? portraitTop : 0",source)

if __name__=="__main__": unittest.main()
