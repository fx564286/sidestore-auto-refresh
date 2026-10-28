"""V144 single native picker: owner-window dismissal + finger lens regression."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v144',ROOT/'scripts/patch_v144_glass_outside.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class GlassPickerTests(unittest.TestCase):
    @staticmethod
    def fixture():
        return '''// SCARLET_V141_OUTSIDE_TAP_DISMISS
// SCARLET_V139_PANEL_TOUCH: optical tracking is decoupled
// SCARLET_V140_FINGER_DEFORMATION
// SCARLET_V131_REFERENCE_LIQUID_GLASS
private final class SCPanelGlassFingerTracker: NSObject, UIGestureRecognizerDelegate {
    weak var rim: SCNativeGlassRimView?
    weak var surface: UIView?

    init(rim: SCNativeGlassRimView, surface: UIView) {
        self.rim = rim
        self.surface = surface
    }
    func track() {
            rim.followPoint(x: x, y: y)
            NSLog("[SCARLET_V139_GLASS] surface=panel finger=tracked")
        case .ended, .cancelled, .failed:
            rim.releasePoint()
        default: break
    }
}
private final class SCNativeGlassRimView: UIView {
        contact.colors = [UIColor.white.withAlphaComponent(0.30).cgColor,
                          UIColor.white.withAlphaComponent(0.08).cgColor,
                          UIColor.white.withAlphaComponent(0.0).cgColor]
}
func presentGlass() {
        let material = UIVisualEffectView(effect: UIGlassEffect(style: .clear))
        material.layer.cornerCurve = .continuous
        let fingerTracker = SCPanelGlassFingerTracker(rim: opticalRim, surface: material.contentView)
        let sourceOrigin = sourceView.convert(sourceView.bounds, to: owner)
        let collapse: (@escaping () -> Void) -> Void = { [weak overlay, weak material, weak sourceView] completion in
            guard let backdrop = overlay, backdrop.superview != nil else { return }
        }
        overlay.addAction(UIAction { _ in
            NSLog("[SCARLET_V141_PICKER] dismiss=outside_tap")
            collapse({})
        }, for: .touchDown)

        if recent.isEmpty {
            return
        }
}'''

    def test_touch_follows_main_glass_and_outside_hits_window(self):
        patched=v.patch(self.fixture())
        self.assertEqual(v.patch(patched),patched)
        self.assertEqual(patched.count(v.MARK),1)
        self.assertIn('SCARLET_V144_LENS_DRAG',patched)
        self.assertIn('SCARLET_V144_GLASS_INSTALLED',patched)
        self.assertIn('owner.addGestureRecognizer(outsideTap)',patched)
        self.assertIn('owner?.removeGestureRecognizer(outsideTap)',patched)
        self.assertIn('panel.convert(panel.bounds, to: owner).contains',patched)
        self.assertIn('lens?.transform = CGAffineTransform(',patched)
        self.assertIn('lens.transform = .identity',patched)
        self.assertIn('outsideTap.cancelsTouchesInView = true',patched)
        self.assertIn('outsideTap.delegate = outsideObserver',patched)
        self.assertIn('let material = UIVisualEffectView(effect: UIGlassEffect(style: .clear))',patched)
        self.assertEqual(patched.count('owner.addGestureRecognizer(outsideTap)'),1)

    def test_preserves_existing_owner(self):
        src=(ROOT/'scripts/patch_v144_glass_outside.py').read_text()
        for bad in ('UIWindow(frame:', 'UIButton(type:', 'SecItemDelete(',
                    'deleteGuest(', 'clearPairing(', 'removeProvisioningProfile('):
            self.assertNotIn(bad,src)

    def test_missing_previous_stage_fails(self):
        with self.assertRaises(ValueError):v.patch('No existing picker')
        with self.assertRaises(ValueError):
            v.patch(self.fixture().replace('SCARLET_V141_OUTSIDE_TAP_DISMISS','missing'))

    def test_patched_real_source(self):
        root=os.getenv('V144_PATCHED_LIVECONTAINER')
        if not root:return
        code=(Path(root)/v.DOCK).read_text()
        self.assertEqual(v.patch(code),code)
        self.assertEqual(code.count(v.MARK),1)
        self.assertIn('SCARLET_V144_LENS_DRAG',code)
        self.assertIn('dismissed=window_outside_tap',code)
        for relative in ('LiveContainer/LCBootstrap.m',
                         'MultitaskSupport/DecoratedAppSceneViewController.m'):
            button=(Path(root)/relative).read_text()
            self.assertEqual(button.count('SCARLET_V144_BUTTON_LENS'),1)

if __name__=='__main__':unittest.main()
