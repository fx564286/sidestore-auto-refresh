"""V141 restores tap on unoccupied UIKit backdrop without new UI owners."""
from pathlib import Path
import importlib.util
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v141outside',ROOT/'scripts/patch_v141_outside_tap.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class OutsideTap(unittest.TestCase):
    def test_outside_tap_closes_on_down(self):
        old='''// SCARLET_V140_MORPH_ANCHOR
// SCARLET_V139_PANEL_TOUCH
// scarlet.v100.morph.backdrop
        overlay.addAction(UIAction { _ in collapse({}) }, for: .touchUpInside)
        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
        NSLog("[SCARLET_V140_GLASS]'''
        new=v.patch(old)
        self.assertIn('SCARLET_V141_OUTSIDE_TAP_DISMISS',new)
        self.assertIn('dismiss=outside_tap',new)
        self.assertIn('for: .touchDown)',new)
        self.assertIn('owner.bringSubviewToFront(overlay)',new)
        self.assertNotIn('for: .touchUpInside)',new)
        self.assertEqual(v.patch(new),new)
    def test_no_new_controls_or_overlays(self):
        src=(ROOT/'scripts/patch_v141_outside_tap.py').read_text()
        self.assertNotIn('UIWindow(frame:',src)
        self.assertNotIn('let overlay = UIControl(',src)
        self.assertNotIn('UITapGestureRecognizer(',src)
    def test_stale_source_is_rejected(self):
        with self.assertRaises(ValueError):v.patch('unknown modal revision')
    def test_actual_source(self):
        root=os.getenv('V141_PATCHED_LIVECONTAINER')
        if not root:return
        body=(Path(root)/v.SOURCE).read_text()
        self.assertEqual(v.patch(body),body)
        self.assertEqual(body.count('SCARLET_V141_OUTSIDE_TAP_DISMISS'),1)
        self.assertIn('dismiss=outside_tap',body)
if __name__=='__main__':unittest.main()
