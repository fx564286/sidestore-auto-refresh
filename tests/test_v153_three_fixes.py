"""V153 source regression: only three issues; V152 panel/tab immutable."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v153",ROOT/"scripts"/"patch_v153_three_fixes.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def unchanged_panel(src):
    a=src.index("        let overlay = UIControl(frame: owner.bounds)")
    b=src.index("        let scroll = UIScrollView()",a)
    return src[a:b]

class V153ThreeFixes(unittest.TestCase):
    def test_rejects_unrelated_patches(self):
        with self.assertRaises(ValueError):m.dock("unrelated code")
        with self.assertRaises(ValueError):m.shell("unrelated code")

    def test_preserves_panel_tabs_and_single_host_picker(self):
        root=os.environ.get("V153_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/m.DOCK).read_text()
        before=os.environ.get("V153_BASELINE_DOCK")
        if before:
            self.assertEqual(unchanged_panel(Path(before).read_text()),
                             unchanged_panel(src))
        self.assertEqual(src.count("SCARLET_V153_THREE_ISSUE_FIX"),1)
        self.assertEqual(src.count("let overlay = UIControl(frame: owner.bounds)"),1)
        self.assertEqual(src.count("let material = UIVisualEffectView(effect:"),1)
        self.assertEqual(src.count("let tabPicker = UISegmentedControl(items:"),1)
        self.assertEqual(src.count('("앱 닫기", "closeWindow")'),1)
        self.assertNotIn('("창 닫기", "closeWindow")',src)
        self.assertEqual(m.dock(src),src)

    def test_recent_button_has_breathing_room_and_no_double_scale(self):
        root=os.environ.get("V153_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/m.DOCK).read_text()
        start=src.index("        } else if !windowActions {\n        for guest in recent {")
        end=src.index("        } else {\n            // Same native system-material panel as recents.",start)
        recent=src[start:end]
        self.assertIn('SCARLET_V153_RECENT_UNCLIPPED',recent)
        self.assertIn('cfg.cornerStyle = .capsule',recent)
        self.assertNotIn('SCGlassControlPress.attach(to: item)',recent)
        self.assertEqual(src.count('scroll.clipsToBounds = windowActions || directMode'),2)
        self.assertIn('rows.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor)',src)
        self.assertNotIn('rows.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor, constant: -18)',src)
        action=src[end:]
        self.assertIn('SCGlassControlPress.attach(to: item)',action)
        self.assertIn('SCARLET_V151_TAB_NATIVE_PRESS',src)

    def test_outside_touch_gesture_is_began_on_overlay_and_guest_windows(self):
        root=os.environ.get("V153_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/m.DOCK).read_text()
        self.assertIn('let outsideTap = SCOutsideTouchDownRecognizer()',src)
        self.assertIn('func install(with primary: SCOutsideTouchDownRecognizer)',src)
        self.assertIn('overlay.addGestureRecognizer(primary)',src)
        self.assertIn('let gesture: UIGestureRecognizer = SCOutsideTouchDownRecognizer()',src)
        self.assertIn('gesture.state == .began',src)
        self.assertIn('dismissQueued = true',src)
        self.assertIn('primary.cancelsTouchesInView = false',src)
        self.assertIn('window.addGestureRecognizer(gesture)',src)
        self.assertIn('installed.removeAll()',src)
        self.assertNotIn('let outsideTap = UITapGestureRecognizer()',src)

    def test_direct_routes_to_original_picker_and_preserves_root_view(self):
        root=os.environ.get("V153_PATCHED_LIVECONTAINER")
        if not root:return
        shell=(Path(root)/m.SHELL).read_text()
        dock=(Path(root)/m.DOCK).read_text()
        self.assertEqual(m.shell(shell),shell)
        route=shell.split("SCARLET_V153_DIRECT_HOST_PICKER:",1)[1]
        self.assertIn('nrgV112PresentDirectGuestUI(',route)
        self.assertIn('from: root, sourceView: root.view',route)
        self.assertNotIn('MultitaskDockManager.shared.nrgV72PresentGuestSwitcher(\n                            from: root, sourceView: root.view)',route)
        self.assertIn('sourceView !== owner.rootViewController?.view',dock)
        self.assertIn('sourceView !== controller.view',dock)
        self.assertIn('[SCARLET_V153_DIRECT] host_anchor_visible=1',dock)
        self.assertNotIn('UIWindow(frame:', (ROOT/"scripts"/"patch_v153_three_fixes.py").read_text())

if __name__=="__main__":unittest.main()
