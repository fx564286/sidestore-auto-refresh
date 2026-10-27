"""V136 fixes split surfaces on orientation transitions without new windows."""
import importlib.util
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v136",ROOT/"scripts/patch_v136_rotation_atomic.py")
v136=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v136)

class RotationAtomic(unittest.TestCase):
    def test_authoritative_host_window_and_safe_geometry(self):
        code=(ROOT/"scripts/patch_v136_rotation_atomic.py").read_text()
        for marker in ("SCARLET_V136_ROTATION_ATOMIC","SCARLET_V136_ROTATION_SETTLE",
                       "parent.convert(bounds, from: hostWindow)",
                       "CGSize viewport", "phase=host_defer", "phase=commit",
                       "UIInterfaceOrientationIsLandscape", "UIInterfaceOrientationIsPortrait",
                       "window.windowScene.interfaceOrientation",
                       "DispatchQueue.main.asyncAfter(deadline: .now() + 0.28)"):
            with self.subTest(marker=marker):self.assertIn(marker,code)
        for bad in ("windowHostingView.removeFromSuperview()", "UIWindow(frame:",
                    "removeFromSuperview]","setAffineTransform:",
                    "self.view.transform =","SecItemDelete"):
            self.assertNotIn(bad,code)
    def test_fail_closed_if_pinned_sources_missing(self):
        for fn in (v136.decorated,v136.dock,v136.delegate):
            with self.assertRaises(ValueError):fn("unrelated")
    def test_real_post_patch_contract(self):
        root=os.environ.get("V136_PATCHED_LIVECONTAINER")
        if not root:return
        root=Path(root)
        a=(root/v136.DECO).read_text()
        b=(root/v136.DOCK).read_text()
        c=(root/v136.DELEGATE).read_text()
        self.assertEqual(v136.decorated(a),a)
        self.assertEqual(v136.dock(b),b)
        self.assertEqual(v136.delegate(c),c)
        self.assertEqual(a.count(v136.MARK),1)
        self.assertEqual(b.count(v136.MARK),1)
        self.assertEqual(c.count("SCARLET_V136_ROTATION_SETTLE"),1)
        self.assertIn("CGSize viewport = self.view.bounds.size;",a)
        self.assertNotIn("BOOL guestIsStale = fabs(guestSize.width - size.width)",a)
        self.assertNotIn("hostScene.windows.first(where: {",b)
        self.assertEqual(c.count("nrgV53ReconcileGuestGeometry(for: windowScene)"),4)
        self.assertIn("SCARLET_V129_VIEWPORT",a)
        self.assertIn("SCARLET_V132_GLASS_DRAG",b)
        self.assertIn("SCARLET_V133_KEYBOARD_HANDOFF",b)

if __name__=="__main__":unittest.main()
