"""Read-only V140 liquid glass/one-panel structural regression."""
from pathlib import Path
import importlib.util
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v140glass',ROOT/'scripts/patch_v140_glass_morph.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class NativeGlassMorphTests(unittest.TestCase):
    def test_single_native_panel_entry_source(self):
        src='''// SCARLET_V139_PANEL_TOUCH
// SCARLET_V139_UNIFIED_GUEST_ACTION
// SCARLET_V131_REFERENCE_LIQUID_GLASS
// SCARLET_V126_INPLACE_TAB_CONTENT
let steadyGlass = UIGlassEffect(style: .clear)
        // SCARLET_V127_COMPLETE_GLASS: keep backdrop light for real glass.
        overlay.backgroundColor = UIColor.black.withAlphaComponent(0.32)
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            overlay.backgroundColor = UIColor.black.withAlphaComponent(0.19)
        }
        let panelWidth = min(352, availableWidth)
        material.layer.cornerRadius = 26
            material.centerYAnchor.constraint(equalTo: overlay.centerYAnchor),
            material.widthAnchor.constraint(equalToConstant: panelWidth),
        material.transform = .identity
        })
        // SCARLET_V131_VISIBLE_GLASS_ACTIVATION retired by V139
        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
    func followPoint(x: CGFloat, y: CGFloat) {
        CATransaction.begin()
        highlight.endPoint = CGPoint(x: min(1, x + 0.22), y: min(1, y + 0.23))
        CATransaction.commit()
    func releasePoint() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        contact.opacity = 0
        CATransaction.commit()
    }
'''
        changed=v.patch(src)
        self.assertEqual(v.patch(changed),changed)
        self.assertEqual(changed.count('SCARLET_V140_MORPH_ANCHOR'),1)
        self.assertEqual(changed.count('SCARLET_V140_FINGER_DEFORMATION'),1)
        self.assertIn('entryFrame = sourceView.convert(sourceView.bounds, to: owner)',changed)
        self.assertIn('constant: panelAnchorOffset',changed)
        self.assertIn('SCARLET_V140_MORPH_ANCHOR',changed)
        self.assertIn('UIColor.clear',changed)
        self.assertIn('UIGlassEffect(style: .clear)',changed)
        self.assertIn('self.transform = CGAffineTransform(translationX: dx, y: dy)',changed)
        self.assertNotIn('material.centerYAnchor.constraint(equalTo: overlay.centerYAnchor),',changed)
        self.assertNotIn('overlay.backgroundColor = UIColor.black.withAlphaComponent(0.19)',changed)
    def test_no_extra_controls_and_no_unsafe_modifications(self):
        src=(ROOT/'scripts/patch_v140_glass_morph.py').read_text()
        for marker in ('UIWindow(frame:', 'UIButton(type:', 'SecItemDelete(',
                       'removeProvisioningProfile(', 'invalidatePairingRecord('):
            self.assertNotIn(marker,src)
    def test_invalid_source_rejected(self):
        with self.assertRaises(ValueError):v.patch('prior glass owner missing')
    def test_compiled_source_if_available(self):
        path=os.getenv('V140_PATCHED_LIVECONTAINER')
        if not path:return
        code=(Path(path)/v.SOURCE).read_text()
        self.assertEqual(v.patch(code),code)
        self.assertEqual(code.count('SCARLET_V140_MORPH_ANCHOR'),1)
        self.assertEqual(code.count('SCARLET_V140_FINGER_DEFORMATION'),1)
        self.assertIn('nrgV72PresentGuestSwitcher',code)
        self.assertNotIn('overlay.backgroundColor = UIColor.black.withAlphaComponent(0.32)',code)
if __name__=='__main__':unittest.main()
