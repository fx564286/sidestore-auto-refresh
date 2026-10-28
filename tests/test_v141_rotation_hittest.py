"""V141: root-level UIKit hit testing after landscape -> portrait."""
from pathlib import Path
import importlib.util
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v141',ROOT/'scripts/patch_v141_rotation_hittest.py')
v141=importlib.util.module_from_spec(spec);spec.loader.exec_module(v141)

class RotationHitTest(unittest.TestCase):
    def test_host_is_never_clipped_inside_swiftui_safe_area_child(self):
        source='''// NRG_V192_SCARLET_STARTUP
// SCARLET_V136_ROTATION_ATOMIC
// SCARLET_V140_MORPH_ANCHOR
// NRG_V58_HOST_WINDOW_GEOMETRY
        guard root.window === window, !root.bounds.isEmpty,
              let anchor = root.subviews.first(where: { !$0.bounds.isEmpty }) else { return }
        guard anchor !== windowHostingView else { return }
        if windowHostingView.superview !== anchor {
            windowHostingView.removeFromSuperview()
            anchor.addSubview(windowHostingView)
            windowHostingView.frame = anchor.bounds
        }
            if let hostWindow = parent.window {
                let bounds = hostWindow.bounds
'''
        changed=v141.dock(source)
        self.assertIn('SCARLET_V141_FULL_ROOT_HITTEST',changed)
        self.assertIn('let anchor: UIView = coversWindow ? root : fullWindow',changed)
        self.assertIn('anchor.convert(fullWindow.bounds, from: fullWindow)',changed)
        self.assertIn('nrgV191AttachGuestWindowHostIfReady()',changed)
        self.assertNotIn('root.subviews.first(where:',changed)
        self.assertEqual(v141.dock(changed),changed)
        self.assertEqual(changed.count('windowHostingView.removeFromSuperview()'),1)

    def test_frame_position_and_insets_are_reconciliation_inputs(self):
        source='''// SCARLET_V136_ROTATION_ATOMIC
// SCARLET_V129_VIEWPORT
@property(nonatomic) UIInterfaceOrientation nrgV55LastHostOrientation;
    if (CGSizeEqualToSize(self.nrgV55LastHostSize, size) &&
        self.nrgV55LastHostOrientation == orientation && !guestIsStale) return;
    self.nrgV55LastHostSize = size;
    self.nrgV55LastHostOrientation = orientation;
    [self.appSceneVC.view setNeedsLayout];
    NSLog(@"[SCARLET_V136_ROTATION] phase=commit'''
        new=v141.decorated(source)
        self.assertIn('SCARLET_V141_INSET_AWARE_SETTLE',new)
        self.assertIn('nrgV141LastWindowInsets',new)
        self.assertIn('!insetChanged && !viewportChanged',new)
        self.assertIn('window.safeAreaInsets',new)
        self.assertIn('phase=viewport_commit',new)
        self.assertEqual(v141.decorated(new),new)

    def test_bounded_safe_area_settle(self):
        source='''// SCARLET_V136_ROTATION_SETTLE
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
'''
        new=v141.delegate(source)
        self.assertIn('SCARLET_V141_ROTATION_SAFEAREA_SETTLE',new)
        self.assertIn('for delay in [0.55, 0.95]',new)
        self.assertIn('windowScene.activationState == .foregroundActive',new)
        self.assertNotIn('Timer.scheduledTimer',new)
        self.assertEqual(v141.delegate(new),new)

    def test_no_guest_reset_or_extra_window(self):
        code=(ROOT/'scripts/patch_v141_rotation_hittest.py').read_text()
        for banned in ('UIWindow(frame:', 'SecItemDelete(', 'deleteGuest(',
                       'application:terminate', 'removeGuest', 'clearPairing('):
            self.assertNotIn(banned,code)

    def test_fail_closed(self):
        for fn in (v141.dock,v141.decorated,v141.delegate):
            with self.assertRaises(ValueError):fn('unrelated source')

    def test_actual_generated_sources_when_available(self):
        root=os.getenv('V141_PATCHED_LIVECONTAINER')
        if not root:return
        root=Path(root)
        for path,fn in ((v141.DOCK,v141.dock),(v141.DECO,v141.decorated),
                        (v141.DELEGATE,v141.delegate)):
            source=(root/path).read_text()
            self.assertEqual(fn(source),source)
        dock=(root/v141.DOCK).read_text()
        deco=(root/v141.DECO).read_text()
        self.assertEqual(dock.count(v141.MARK),1)
        self.assertEqual(deco.count('SCARLET_V141_INSET_AWARE_SETTLE'),1)
        self.assertNotIn('let anchor = root.subviews.first(where:',dock)
        self.assertIn('nrgV141LastViewportFrame',deco)

if __name__=='__main__':unittest.main()
