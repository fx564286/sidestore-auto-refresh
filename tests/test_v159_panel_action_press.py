"""V159 pixel-layout contract: two tabs retain one exact native-glass
panel size, and window action long-press does not transform UIKit clearGlass.

Source tests only, not a substitute for physical-device verification.
"""
from pathlib import Path
import importlib.util, os, unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v159",ROOT/"scripts"/"patch_v159_panel_height_native_action.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class V159NoActionClipping(unittest.TestCase):
    def test_missing_source_fails_closed(self):
        with self.assertRaises(ValueError):m.patch("unrelated")

    def test_exact_same_outer_panel_and_native_top_tabs_as_successful_v158(self):
        root=os.getenv("V159_PATCHED_LIVECONTAINER")
        baseline=os.getenv("V159_BASELINE_DOCK")
        if not root or not baseline:return
        new=(Path(root)/m.DOCK).read_text()
        old=Path(baseline).read_text()
        a="        let material = UIVisualEffectView(effect:"
        b="        let scroll = UIScrollView()"
        self.assertEqual(new[new.index(a):new.index(b)],
                         old[old.index(a):old.index(b)])
        for x in ("SCARLET_V157_WIDE_PANEL", "SCARLET_V158_EQUAL_TAB_FRAME",
                  "SCARLET_V158_EQUAL_ROW_GEOMETRY","SCARLET_V156_OUTSIDE_TOUCH_TRACE",
                  "SCARLET_V155_DOCK_SINGLE_MODE"):
            self.assertIn(x,new)
        self.assertEqual(m.patch(new),new)

    def test_actual_height_constraint_frozen_across_tab_switch(self):
        root=os.getenv("V159_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/m.DOCK).read_text()
        self.assertIn("SCARLET_V159_PINNED_OUTER_FRAME",src)
        self.assertIn("var stablePanelHeight: CGFloat = 0",src)
        self.assertLess(src.index("var stablePanelHeight: CGFloat = 0"),
                        src.index("tabPicker.addAction(UIAction"))
        self.assertIn("stablePanelHeight = material.bounds.height",src)
        self.assertIn("let frozenHeight = material.heightAnchor.constraint(equalToConstant: stablePanelHeight)",src)
        self.assertIn("frozenHeight.priority = .required",src)
        self.assertIn("frozenHeight.isActive = true",src)
        self.assertIn("tabListHeightConstraint.constant = listHeight",src)
        self.assertIn("SCARLET_V159_PANEL_EQUAL",src)
        self.assertNotIn("CGFloat(max(1, recent.count)) * 54 + 24",src)
        self.assertEqual(src.count("material.widthAnchor.constraint(equalToConstant: panelWidth)"),1)

    def test_three_actions_have_system_glass_without_double_scaling(self):
        root=os.getenv("V159_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/m.DOCK).read_text()
        start=src.index('let actions: [(String, String)] = [')
        end=src.index('''        }

        }
        rebuildTabContent()''',start)
        actions=src[start:end]
        self.assertIn('("최소화", "minimizeWindow")',actions)
        self.assertIn('("최대화 / 복원", "maximizeWindow")',actions)
        self.assertIn('("앱 닫기", "closeWindow")',actions)
        self.assertIn("UIButton.Configuration.clearGlass()",actions)
        self.assertIn("config.cornerStyle = .capsule",actions)
        self.assertIn("SCGlassControlPress.attach(to: item, nativeOnly: true)",actions)
        self.assertNotIn("SCGlassControlPress.attach(to: item)\n",actions)
        self.assertIn('if nativeOnly {',src)
        self.assertIn('phase=began transform=identity',src)
        self.assertIn('phase=released transform=identity',src)

    def test_no_duplicate_picker_or_window_or_buttons(self):
        root=os.getenv("V159_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/m.DOCK).read_text()
        self.assertEqual(src.count('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)'),1)
        self.assertEqual(src.count('let tabPicker = UISegmentedControl(items:'),1)
        self.assertEqual(src.count('SCGlassControlPress.attach(to: item, nativeOnly: true)'),1)
        self.assertIn("scroll.clipsToBounds = false",src)
        self.assertNotIn("@objc(SCUnifiedGuestUIBridge)",src)

if __name__=="__main__":unittest.main()
