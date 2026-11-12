"""P18: real guest descendant geometry is measured without changing the UI.

The P17 device runtime proved 2 armed processes and 7 already-safe 62pt
roots. The absence of `guest_root_corrected` is not a reason to add insets.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
GUEST=(ROOT/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
HOST=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
REC=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()

class GuestDescendantObservationContracts(unittest.TestCase):
    def test_only_guest_already_safe_root_schedules_bounded_readbacks(self):
        self.assertIn('ScarletIslandScheduleContentProbe(window, root, target);', GUEST)
        self.assertIn('if(before >= target - 2)', GUEST)
        self.assertIn('for(NSNumber *delay in @[@650, @2600])', GUEST)
        self.assertIn('objc_getAssociatedObject(root, &scarletIslandContentProbeKey)', GUEST)
        self.assertIn('ScarletIslandContentProbe(weakWindow, weakRoot, expectedTop, sample)', GUEST)
        self.assertIn('window.rootViewController != expectedRoot', GUEST)

    def test_sampling_is_bounded_nonmutating_and_window_coordinate_based(self):
        self.assertIn('metrics->visited >= 1200',GUEST)
        self.assertIn('depth > 24',GUEST)
        self.assertIn('convertRect:view.bounds toView:window',GUEST)
        self.assertIn('rootView.safeAreaLayoutGuide.layoutFrame',GUEST)
        self.assertIn('CGRectGetMinY(guideFrame)',GUEST)
        helper=GUEST.split('// R6P18: root Safe Area was already 62pt',1)[1].split('static void ScarletIslandInspect',1)[0]
        for forbidden in ['root.additionalSafeAreaInsets =', 'window.frame =', 'method_exchangeImplementations(', 'setNeedsLayout', 'layoutIfNeeded', 'UIView animateWithDuration']:
            self.assertNotIn(forbidden,helper)

    def test_guest_metrics_cover_top_controls_and_scroll_regions_without_labels(self):
        self.assertIn('UIAccessibilityTraitButton',GUEST)
        self.assertIn('[view isKindOfClass:UIControl.class]',GUEST)
        self.assertIn('[view isKindOfClass:UIScrollView.class]',GUEST)
        self.assertIn('scroll.adjustedContentInset.top',GUEST)
        self.assertIn('metrics->unsafeControls++',GUEST)
        self.assertIn('metrics->capped = YES',GUEST)
        for forbidden in ['accessibilityLabel', 'accessibilityHint', 'NSStringFromClass(', 'bundleIdentifier', 'screenshot', 'UIGraphicsImageRenderer']:
            self.assertNotIn(forbidden,GUEST.split('typedef struct',1)[1])

    def test_every_emitted_numeric_key_is_whitelisted(self):
        for key in ['sample_index','root_frame_y','root_guide_y','visited',
                    'candidate_controls','top_controls','unsafe_controls',
                    'first_top_control_y','first_unsafe_control_y',
                    'scroll_top_without_inset','scan_capped','root_safe_top_pt']:
            self.assertIn('"'+key+'"',HOST)
            self.assertIn('"'+key+'"',REC)
        self.assertIn('"guest_content_geometry_probe", fields: fields',HOST)
        self.assertIn('@"result":@"guest_content_geometry_probe"',GUEST)
        self.assertIn('if result == "guest_content_geometry_probe"',HOST)

    def test_existing_root_correction_is_identical_to_p17(self):
        self.assertIn('CGFloat deficit = MIN(130, MAX(0, target - before));',GUEST)
        self.assertIn('root.additionalSafeAreaInsets = extra;',GUEST)
        self.assertIn('guest_root_already_safe',GUEST)
        self.assertIn('guest_root_guard_armed',GUEST)
        self.assertIn('NSUserDefaults.lcUserDefaults',GUEST)

    def test_probe_does_not_assume_undetected_virtual_elements_are_safe(self):
        self.assertIn('Zero candidates never proves no overlap',GUEST)
        self.assertIn('if(!window || window.hidden || window.rootViewController != expectedRoot',GUEST)
        self.assertIn('if(!rootView || rootView.window != window) return;',GUEST)
        self.assertIn('firstUnsafeControlY == NSIntegerMax ? -999',GUEST)

if __name__=='__main__':unittest.main()
