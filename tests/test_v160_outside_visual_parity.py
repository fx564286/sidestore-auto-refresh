"""V160 source contract; device event routing still needs physical verification."""
import importlib.util
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v160', ROOT / 'scripts' / 'patch_v160_outside_visual_parity.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class V160VisualAndOutsideContract(unittest.TestCase):
    def test_unknown_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'missing prerequisite'):
            m.patch('irrelevant')

    def test_generated_single_panel_and_outside_return(self):
        root = os.getenv('V160_PATCHED_LIVECONTAINER')
        if not root:
            return
        s = (Path(root) / m.DOCK).read_text(encoding='utf-8')
        self.assertEqual(m.patch(s), s)
        self.assertEqual(s.count('SCARLET_V160_OUTSIDE_RETURN'), 2)  # comment + log
        self.assertIn('self.dismissOutside?()', s)
        self.assertIn('phase=outside_down', s)
        self.assertIn('return\n            }\n        }\n        super.touchesBegan', s)
        self.assertIn('panel.convert(panel.bounds, to: self).contains(point)', s)
        self.assertIn('let panelWindow = panel.window', s)
        self.assertIn('panelWindow.screen.coordinateSpace', s)
        self.assertNotIn('panel?.window === owner else { return }', s)
        self.assertEqual(s.count('let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)'), 1)
        self.assertEqual(s.count('let tabPicker = UISegmentedControl(items:'), 1)

    def test_18pt_tab_and_action_alignment(self):
        root = os.getenv('V160_PATCHED_LIVECONTAINER')
        if not root:
            return
        s = (Path(root) / m.DOCK).read_text(encoding='utf-8')
        for x in ('tabPicker.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18)',
                  'tabPicker.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor, constant: -18)',
                  'tabRim.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18)',
                  'tabRim.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor, constant: -18)',
                  'rows.layoutMargins = UIEdgeInsets(top: 0, left: 18, bottom: 0, right: 18)'):
            self.assertIn(x, s)
        self.assertEqual(s.count('SCARLET_V160_BUTTON_RIM'), 2)
        self.assertIn('UIColor.secondarySystemBackground.withAlphaComponent(0.16)', s)
        self.assertIn('UIColor.tertiarySystemFill', s)
        self.assertIn('UIButton.Configuration.clearGlass()', s)
        self.assertNotIn('private final class SCGuestMorphPresenter', s)


if __name__ == '__main__':
    unittest.main()
