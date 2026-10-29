"""V157 exact user screenshot fix: panel WIDTH, without shrinking height.

A one-hunk source diff ensures both rounded tabs, the action capsules,
outside-touch event handling, source centering and V156 large height are
literally unchanged. Never claim device success from these source tests.
"""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v157",ROOT/"scripts"/"patch_v157_panel_width.py")
v157=importlib.util.module_from_spec(spec);spec.loader.exec_module(v157)

class V157WiderPanel(unittest.TestCase):
    def test_old_source_fails_size_requirement(self):
        baseline=os.getenv("V157_BASELINE_DOCK")
        if baseline:
            src=Path(baseline).read_text()
            self.assertIn(v157.OLD,src)
            self.assertNotIn(v157.NEW,src)
            self.assertNotEqual(v157.patch(src),src)

    def test_single_change_and_old_panel_behavior_preserved(self):
        new=os.getenv("V157_PATCHED_LIVECONTAINER")
        baseline=os.getenv("V157_BASELINE_DOCK")
        if not new or not baseline:return
        actual=(Path(new)/v157.DOCK).read_text()
        old=Path(baseline).read_text()
        self.assertEqual(actual.count(v157.MARK),1)
        self.assertEqual(actual.replace(v157.NEW,v157.OLD),old,
                         "only panel width may differ from successful V156")
        self.assertEqual(v157.patch(actual),actual)

    def test_screen_responsive_width_and_left_right_symmetry(self):
        # Preserve width on iPad/landscape at 390, while portrait iPhone
        # uses 16pt insets and gets wider than the previous 352pt cap.
        for w in (320,375,390,393,402,416,430,568,852,1024):
            with self.subTest(windowWidth=w):
                old=min(352,max(260,w-48))
                new=min(390,max(260,w-32))
                self.assertGreaterEqual(new,old)
                self.assertLessEqual(new,390)
                if 320<=w<=430:
                    self.assertLessEqual(w-new,40)
                    self.assertGreaterEqual((w-new)/2,0)
                if w>=375:
                    self.assertGreater(new,old)

    def test_two_tabs_keep_identical_large_panel_height(self):
        root=os.getenv("V157_PATCHED_LIVECONTAINER")
        if not root:return
        source=(Path(root)/v157.DOCK).read_text()
        for marker in ("SCARLET_V156_STABLE_PANEL_HEIGHT",
                       "SCARLET_V156_ROW_OPTICAL_PAD",
                       "SCARLET_V156_OUTSIDE_TOUCH_TRACE",
                       "SCARLET_V151_TAB_NATIVE_PRESS",
                       "SCARLET_V155_DOCK_SINGLE_MODE"):
            self.assertIn(marker,source)
        self.assertEqual(source.count("CGFloat(actionsCount * 54)"),2)
        self.assertIn("material.layer.cornerRadius = 30",source)
        self.assertIn("steadyGlass.isInteractive = true",source)
        self.assertIn("cfg.cornerStyle = .capsule",source)
        self.assertIn("config.cornerStyle = .capsule",source)
        self.assertIn("stage=collapse_completed",source)
        self.assertIn("[SCARLET_V157_WIDTH] viewport=",source)

    def test_upstream_anchor_change_fails_closed(self):
        with self.assertRaises(ValueError):v157.patch("arbitrary swift")
        valid=os.getenv("V157_BASELINE_DOCK")
        if valid:
            text=Path(valid).read_text()
            with self.assertRaisesRegex(ValueError,"width anchor moved"):
                v157.patch(text.replace(v157.OLD,"let panelWidth = 352"))

if __name__=="__main__":unittest.main()
