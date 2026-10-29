"""V158 regression: two tabs share one non-shrinking window-action frame,
and native glass action buttons have room to expand without edge cropping.

The source tests do not claim on-device success.
"""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v158",ROOT/"scripts"/"patch_v158_unified_action_glass.py")
v158=importlib.util.module_from_spec(spec);spec.loader.exec_module(v158)

class EqualPanelUnclippedActionGlass(unittest.TestCase):
    def test_reject_unknown_source(self):
        with self.assertRaises(ValueError):
            v158.patch("random swift")

    def test_shared_action_height_and_no_shrink_with_recent_count(self):
        root=os.getenv("V158_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/v158.FILE).read_text()
        self.assertEqual(src.count("let listHeight = min(CGFloat(actionsCount * 54), maxListHeight)"),1)
        self.assertEqual(src.count("tabListHeightConstraint.constant = listHeight"),1)
        self.assertIn("SCARLET_V158_EQUAL_TAB_FRAME",src)
        self.assertNotIn("CGFloat(max(1, recent.count)) * 54 + 24",src)
        # Both tabs use the same 3-action viewport for 0..10 recent apps.
        for apps in range(11):
            action_rows=3
            expected=min(action_rows*54,500)
            self.assertEqual(expected,162)
            self.assertEqual(expected,min(action_rows*54,500))
        self.assertEqual(v158.patch(src),src)

    def test_window_actions_unclipped_but_external_pane_unchanged(self):
        root=os.getenv("V158_PATCHED_LIVECONTAINER")
        base=os.getenv("V158_BASELINE_DOCK")
        if not root or not base:return
        current=(Path(root)/v158.FILE).read_text()
        before=Path(base).read_text()
        a="        let material = UIVisualEffectView(effect:"
        b="        let scroll = UIScrollView()"
        self.assertEqual(current[current.index(a):current.index(b)],
                         before[before.index(a):before.index(b)],
                         "panel width, 30pt corners, native Glass tabs must be exact")
        self.assertIn("SCARLET_V157_WIDE_PANEL",current)
        self.assertIn("SCARLET_V151_TAB_NATIVE_PRESS",current)
        self.assertIn("material.clipsToBounds = true",current)
        self.assertEqual(current.count("scroll.clipsToBounds = false"),2)
        self.assertNotIn("scroll.clipsToBounds = windowActions",current)

    def test_action_press_has_intrinsic_edge_clearance_without_size_change(self):
        root=os.getenv("V158_PATCHED_LIVECONTAINER")
        if not root:return
        s=(Path(root)/v158.FILE).read_text()
        self.assertIn("SCARLET_V158_ACTION_INSETS",s)
        self.assertIn("SCARLET_V158_ACTION_UNCLIPPED",s)
        self.assertIn("UIEdgeInsets(top: 0, left: 18, bottom: 0, right: 18)",s)
        self.assertIn("UIEdgeInsets(top: 12, left: 18, bottom: 12, right: 18)",s)
        self.assertEqual(s.count("rows.isLayoutMarginsRelativeArrangement = true"),2)
        self.assertEqual(s.count("SCGlassControlPress.attach(to: item)"),1)
        self.assertIn('("최소화", "minimizeWindow")',s)
        self.assertIn('("최대화 / 복원", "maximizeWindow")',s)
        self.assertIn('("앱 닫기", "closeWindow")',s)
        self.assertEqual(s.count("item.heightAnchor.constraint(equalToConstant: 47)"),2)
        # Action buttons still spring on hold and retract on release.
        self.assertIn("control.transform = CGAffineTransform(scaleX: 1.020, y: 1.025)",s)
        self.assertIn("animations: { control.transform = .identity }",s)

    def test_no_new_overlay_or_direct_path(self):
        root=os.getenv("V158_PATCHED_LIVECONTAINER")
        if not root:return
        s=(Path(root)/v158.FILE).read_text()
        self.assertEqual(s.count('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)'),1)
        self.assertEqual(s.count("let tabPicker = UISegmentedControl(items:"),1)
        self.assertEqual(s.count("material.widthAnchor.constraint(equalToConstant: panelWidth)"),1)
        self.assertNotIn("@objc(SCUnifiedGuestUIBridge)",s)
        self.assertNotIn("nrgV112PresentDirectGuestUI(",s)
        for marker in ("SCARLET_V156_OUTSIDE_TOUCH_TRACE",
                       "stage=collapse_completed",
                       "SCARLET_V155_DOCK_SINGLE_MODE"):
            self.assertIn(marker,s)

    def test_integration_is_one_hunk_per_contract_and_idempotent(self):
        root=os.getenv("V158_PATCHED_LIVECONTAINER")
        if not root:return
        src=(Path(root)/v158.FILE).read_text()
        self.assertEqual(src.count(v158.MARK),1)
        self.assertEqual(v158.patch(src),src)
        with self.assertRaisesRegex(ValueError,"partial"):
            v158.patch(v158.MARK+"// broken")

if __name__=="__main__":
    unittest.main()
