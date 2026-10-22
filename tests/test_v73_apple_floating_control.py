"""V73: Apple-native movable control avoids guest top-right navigation touches."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
v37=load('patch_v37_window_overflow')
v72=load('patch_v72_overflow_longpress')
v73=load('patch_v73_apple_floating_control')

class V73FloatingControlTests(unittest.TestCase):
    def test_native_adaptive_appearance(self):
        text=v73.MATERIAL
        for expected in ('UIVisualEffectView', 'UIBlurEffectStyleSystemThinMaterial',
                         'UIColor.labelColor','overflow.layer.cornerRadius = 22.0',
                         'overflow.backgroundColor = UIColor.clearColor',
                         'overflow.accessibilityHint',
                         'nrgV73Material.userInteractionEnabled = NO'):
            self.assertIn(expected,text)
        self.assertNotIn('blackColor',text)
        self.assertNotIn('dynamicIsland',text)

    def test_safe_movable_default_never_fixed_upper_right(self):
        s=v73.METHODS
        for expected in ('[self nrgV73MinY]','[self nrgV73MaxY]',
                         'self.view.window.safeAreaInsets.top',
                         'self.view.window.safeAreaInsets.bottom',
                         'maxY > minY ?',
                         'self.nrgV73FloatingLeading.constant = onRight ?',
                         'nrgV73DragFloatingOverflow:',
                         'UIGestureRecognizerStateChanged',
                         'UIGestureRecognizerStateCancelled',
                         'UISelectionFeedbackGenerator',
                         'usingSpringWithDamping:0.82',
                         'fraction = [stored isKindOfClass:NSNumber.class] ? [stored doubleValue] : 0.60',
                         '@"portrait"','@"landscape"'):
            self.assertIn(expected,s)
        self.assertIn('self.nrgV73FloatingLeading.constant = onRight ? MAX(8.0, size.width - 52.0) : 8.0;',s)
        self.assertNotIn('constant:-8',v73.CONSTRAINTS)
        self.assertNotIn('safeAreaLayoutGuide.topAnchor constant:6',v73.CONSTRAINTS)
        self.assertIn('constraintEqualToConstant:44',v73.CONSTRAINTS)

    def test_tap_hold_drag_independent(self):
        text=v73.GESTURE
        self.assertIn('UIPanGestureRecognizer',text)
        self.assertNotIn('self.view addGestureRecognizer',text)
        self.assertIn('[overflow addGestureRecognizer:nrgV73Drag]',text)
        pinned=self.pinned()
        if not pinned.exists():self.skipTest('pinned LiveContainer source missing')
        source=pinned.read_text()
        if v73.MARK not in source:
            if v72.MARK not in source:
                source=v72.patch_window(v37.patch(source))
        self.assertIn('overflow.showsMenuAsPrimaryAction = YES',source)

    @staticmethod
    def pinned():
        if os.environ.get('LIVE_CONTAINER_TEST_SOURCE'):
            return Path(os.environ['LIVE_CONTAINER_TEST_SOURCE'])/v73.FILE
        return Path('/workspace/scarlet-v65/pinned-livecontainer/MultitaskSupport/DecoratedAppSceneViewController.m')

    def test_composed_real_source_and_repeatability(self):
        pinned=self.pinned()
        if not pinned.exists():self.skipTest('pinned LiveContainer source missing')
        s=pinned.read_text()
        if v73.MARK in s:
            updated=v73.patch(s)
        else:
            if v72.MARK not in s:
                s=v72.patch_window(v37.patch(s))
            updated=v73.patch(s)
        self.assertEqual(updated,v73.patch(updated))
        self.assertIn('nrgV72WindowOverflowLongPress',updated)
        self.assertIn('nrgV73DragFloatingOverflow:',updated)
        self.assertEqual(1,updated.count(v73.MARK))
        self.assertNotIn('overflow.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-8',updated)
        self.assertNotIn('constant:34',updated.split('self.nrgV73FloatingLeading =',1)[1].split('- (void)nrgV72',1)[0])
        self.assertIn('viewDidLayoutSubviews',updated)
        self.assertIn('[super viewDidLayoutSubviews]',updated)
        self.assertIn('NSLayoutConstraint',updated)
        self.assertIn('overflow.menu = [UIMenu menuWithChildren:',updated)
        for action in ('minimizeWindow','maximizeWindow','closeWindow'):
            self.assertIn(action,updated)

    def test_ci_patched_source(self):
        root=os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        if not root or os.environ.get('V73_PATCHED_LIVECONTAINER') != '1':return
        target=Path(root)/v73.FILE
        s=target.read_text()
        self.assertIn(v73.MARK,s)
        self.assertEqual(s,v73.patch(s))
        self.assertNotIn('overflow.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-8',s)

if __name__=='__main__':unittest.main()
