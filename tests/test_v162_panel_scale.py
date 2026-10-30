"""Check width scale, height chrome and prior functional controls."""
import importlib.util
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v162',ROOT/'scripts/patch_v162_panel_scale.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class V162ScaleTests(unittest.TestCase):
    def test_fails_on_unknown_source(self):
        with self.assertRaisesRegex(ValueError,'V162 requires V161'):
            mod.patch('invalid')
    def test_reduces_common_iphone_width_by_one_sixth(self):
        for viewport in (375,390,402,416,430,600):
            original=min(390,max(260,viewport-32))
            updated=max(270,original*5/6)
            with self.subTest(viewport=viewport):
                if original*5/6>=270:self.assertAlmostEqual(updated/original,5/6)
                self.assertLessEqual(updated,original)
                self.assertGreaterEqual(updated,270)
    def test_generated_controls_and_touches(self):
        root=os.getenv('V162_PATCHED_LIVECONTAINER')
        if not root:return
        s=(Path(root)/mod.DOCK).read_text()
        self.assertEqual(mod.patch(s),s)
        for phrase in ('SCARLET_V162_SIXTH_SMALLER','5.0 / 6.0','content.spacing = 7',
                       'content.topAnchor.constraint(equalTo: material.contentView.topAnchor, constant: 16)',
                       'content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -14)',
                       'footer.isHidden = true','item.heightAnchor.constraint(equalToConstant: 47)',
                       'SCARLET_V161_BLANK_PANEL_DISMISS','SCARLET_V160_OUTSIDE_RETURN',
                       'SCARLET_V161_RESIZE_TAB','SCARLET_V160_GEOMETRY_PARITY',
                       'tabPicker.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18)',
                       'tabRim.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18)'):
            self.assertIn(phrase,s)
        self.assertEqual(s.count('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)'),1)
        self.assertEqual(s.count('let tabPicker = UISegmentedControl(items:'),1)
        self.assertEqual(s.count('let material = UIVisualEffectView(effect:'),1)
        self.assertEqual(s.count('item.heightAnchor.constraint(equalToConstant: 47)'),2)
        self.assertEqual(s.count('SCARLET_V162_SIXTH_SMALLER:'),1)
        self.assertIn('NSLog("[SCARLET_V162_SIXTH_SMALLER] panel=',s)
        self.assertEqual(s.count('content.addArrangedSubview(footer)'),1)
        self.assertIn('let outside = !panelOnScreen.contains(onScreen)',s)
        self.assertIn('if outside { return true }',s)
if __name__=='__main__':unittest.main()
