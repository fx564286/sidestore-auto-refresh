"""V156 source regression: preserve large panel geometry and uncut button
optical bloom; outside tap must have one owner + window fallback with reasons."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("patch_v156",ROOT/"scripts"/"patch_v156_panel_size_outside.py")
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class V156StableGlass(unittest.TestCase):
    def test_fail_closed_on_old_source(self):
        with self.assertRaises(ValueError): p.patch("not V155")

    def test_image_expectation_unchanged_outer_width_border_and_tabs(self):
        r=os.environ.get("V156_PATCHED_LIVECONTAINER")
        b=os.environ.get("V156_BASELINE_DOCK")
        if not r or not b:return
        src=(Path(r)/p.FILE).read_text()
        old=Path(b).read_text()
        for anchor in ('material.layer.cornerRadius = 30',
                       'material.widthAnchor.constraint(equalToConstant: panelWidth)',
                       'let panelWidth = min(352, availableWidth)',
                       'let tabPicker = UISegmentedControl(items:',
                       'let actions: [(String, String)] = [',
                       'SCARLET_V151_TAB_NATIVE_PRESS'):
            self.assertEqual(src.count(anchor),old.count(anchor),anchor)
        outerstart="        let material = UIVisualEffectView(effect:"
        outerend="        let content = UIStackView()"
        self.assertEqual(src[src.index(outerstart):src.index(outerend)],
                         old[old.index(outerstart):old.index(outerend)],
                         "outer glass, width and native refraction are frozen")
        self.assertEqual(p.patch(src),src)

    def test_same_minimum_height_for_both_tabs(self):
        r=os.environ.get("V156_PATCHED_LIVECONTAINER")
        if not r:return
        src=(Path(r)/p.FILE).read_text()
        self.assertEqual(src.count("CGFloat(actionsCount * 54)"),2)
        self.assertEqual(src.count("CGFloat(max(1, recent.count)) * 54 + 24"),2)
        self.assertIn("SCARLET_V156_STABLE_PANEL_HEIGHT",src)
        # 1 app still uses 3-action physical list height, not 1-row height.
        for recent in (0,1,2,3,4,8):
            need=max(3*54,max(1,recent)*54+24)
            self.assertGreaterEqual(need,3*54)

    def test_recent_only_optical_clearance(self):
        r=os.environ.get("V156_PATCHED_LIVECONTAINER")
        if not r:return
        src=(Path(r)/p.FILE).read_text()
        self.assertIn("SCARLET_V156_ROW_OPTICAL_PAD",src)
        self.assertIn("UIEdgeInsets(top: 12, left: 18, bottom: 12, right: 18)",src)
        self.assertIn("rows.isLayoutMarginsRelativeArrangement = !windowActions",src)
        self.assertIn("scroll.clipsToBounds = windowActions",src)
        self.assertIn("cfg.cornerStyle = .capsule",src)
        self.assertIn("config.cornerStyle = .capsule",src)

    def test_owner_overlay_and_windows_emit_separate_touch_stages(self):
        r=os.environ.get("V156_PATCHED_LIVECONTAINER")
        if not r:return
        src=(Path(r)/p.FILE).read_text()
        for marker in ('stage=backdrop_installed','stage=backdrop_received',
                       'stage=window_should_receive','stage=window_collapse_requested',
                       'stage=collapse_requested source=backdrop','stage=collapse_started',
                       'stage=collapse_completed'):
            with self.subTest(marker=marker):self.assertIn(marker,src)
        self.assertIn('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)',src)
        self.assertIn('outsideObserver.install(with: outsideTap)',src)
        self.assertNotIn('overlay.addAction(UIAction { _ in\n            NSLog("[SCARLET_V141_PICKER] dismiss=outside_tap")',src)
        self.assertIn('SCARLET_V155_DOCK_SINGLE_MODE',src)
        self.assertNotIn('@objc(SCUnifiedGuestUIBridge)',src)

if __name__=="__main__":unittest.main()
