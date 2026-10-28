"""V151 interactive capsule glass, low-bloom press, immutable native panel."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v151_polish",ROOT/"scripts"/"patch_v151_glass_polish.py")
patcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

def panel_section(s):
    a=s.index("        let material = UIVisualEffectView(effect:")
    b=s.index("        let tabPicker = UISegmentedControl(items:",a)
    return s[a:b]

class V151GlassPolishTest(unittest.TestCase):
    def test_patch_fails_on_wrong_baseline(self):
        with self.assertRaises(ValueError):
            patcher.patch("old unrelated Swift")

    def test_source_does_not_replace_panel_or_add_window(self):
        s=(ROOT/"scripts"/"patch_v151_glass_polish.py").read_text()
        self.assertNotIn("let material = UIVisualEffectView(effect:",s)
        self.assertNotIn("let overlay = UIControl(frame:",s)
        self.assertNotIn("UIWindow(frame:",s)
        self.assertNotIn("UIVisualEffectView(effect: UIGlassEffect(",s)

    def test_generated_source_is_capsule_and_idempotent(self):
        root=os.environ.get("V151_PATCHED_LIVECONTAINER")
        if not root:
            self.assertEqual(patcher.DOCK.name,"MultitaskDockView.swift")
            return
        s=(Path(root)/patcher.DOCK).read_text()
        self.assertEqual(patcher.patch(s),s)
        self.assertEqual(s.count("SCARLET_V151_CAPSULE_INTERACTIVE_GLASS"),1)
        self.assertEqual(s.count("cornerStyle = .capsule"),3)
        self.assertEqual(s.count("SCGlassControlPress.attach(to: item)"),3)
        self.assertNotIn("SCGlassControlPress.attach(to: tabPicker)",s)
        self.assertIn("[SCARLET_V151_TAB_NATIVE_PRESS] native_thumb=1",s)
        self.assertIn("[SCARLET_V151_ROW_PRESS] phase=pressed",s)
        self.assertIn("SCARLET_V151_PANEL_STATIC_TOUCH",s)
        self.assertNotIn(".scaledBy(x: 1.055, y: 1.105)",s)
        self.assertIn("scaleX: 1.020, y: 1.025",s)
        self.assertEqual(s.count('("앱 닫기", "closeWindow")'),1)
        self.assertNotIn('("창 닫기", "closeWindow")',s)
        self.assertIn("SCARLET_V150_OUTSIDE_TOUCH_DOWN",s)
        self.assertIn("SCARLET_V150_LONG_PRESS",s)
        base=os.environ.get("V151_BASELINE_DOCK")
        if base:
            before=Path(base).read_text()
            self.assertEqual(panel_section(before),panel_section(s),
                             "original morph panel geometry/effect must not change")

    def test_no_finger_pan_on_system_segmented_control(self):
        root=os.environ.get("V151_PATCHED_LIVECONTAINER")
        if not root:return
        s=(Path(root)/patcher.DOCK).read_text()
        a=s.index("let tabPicker = UISegmentedControl(items:")
        b=s.index("let scroll = UIScrollView()",a)
        block=s[a:b]
        self.assertNotIn("glassPan",block)
        self.assertNotIn("glassTracking",block)
        self.assertNotIn("tabPicker.addGestureRecognizer(",block)
        self.assertIn("SCARLET_V151_TAB_NATIVE_PRESS",block)
        self.assertIn("tabPicker.selectedSegmentTintColor",block)

if __name__=="__main__":
    unittest.main()
