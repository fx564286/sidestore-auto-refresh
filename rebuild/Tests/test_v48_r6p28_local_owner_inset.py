"""R6P28 regression: narrow real local-safe-area repair, no window/UI reset.

R6P27 iPhone PID8274: two nearest scroll owners, the dominant one begins
at UIWindow y50 with local safeTop12 and adjusted top3, offset-3 and
never adjustment. Original L063 selected no scroller among 5.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()

def local_delta(root_safe: float, frame_y: float, local_safe: float,
                adjusted: float, never=True, at_rest=True):
    if abs(frame_y + local_safe - root_safe) > 3:
        return None
    deficit = __import__("math").ceil(local_safe - adjusted)
    if not 4 <= deficit <= 24 or not never or not at_rest:
        return None
    return deficit

class LocalOwnerInsets(unittest.TestCase):
    def test_observed_local_gap_not_whole_root(self):
        self.assertEqual(local_delta(62, 50, 12, 3), 9)
        self.assertIsNone(local_delta(62, 50, 12, 12))
        self.assertIsNone(local_delta(62, 50, 12, 3, never=False))
        self.assertIsNone(local_delta(62, 50, 12, 3, at_rest=False))
        self.assertIsNone(local_delta(62, 0, 12, 3))
        self.assertIsNone(local_delta(62, 50, 62, 3))
        self.assertIsNone(local_delta(62, 50, 12, -30))

    def test_unique_nearest_visible_owner_not_global_scroll_eligible(self):
        fix = G.split('// R6P28: unique visible control owner',1)[1].split(
            'void initScarletGuestIslandContentGuard',1)[0]
        for required in ('ScarletIslandWalkViews(rootView, window, expectedTop',
                         'metrics.visibleUnsafeControls < 2',
                         'selectedControls < 2 || ambiguous',
                         'groups.count','owner.safeAreaInsets.top',
                         'fabs(y + localSafeTop - expectedTop) <= 3',
                         'UIScrollViewContentInsetAdjustmentNever',
                         'owner.contentSize.height <= owner.bounds.size.height + 24',
                         'fabs(owner.contentOffset.y + before) <= 2',
                         'deficit >= 4 && deficit <= 24',
                         'inset.top += deficit','owner.contentOffset = offset',
                         'write_readback_rollback','guest_local_owner_inset_applied',
                         '&scarletIslandLocalOwnerAppliedKey',
                         '(int64_t)1100 * NSEC_PER_MSEC'):
            self.assertIn(required,fix)

    def test_no_global_ui_mutation_and_original_guard_retained(self):
        fix = G.split('// R6P28: unique visible control owner',1)[1].split(
            'void initScarletGuestIslandContentGuard',1)[0]
        for forbidden in ('window.frame =', 'view.frame =',
                          'root.additionalSafeAreaInsets =',
                          'contentInsetAdjustmentBehavior =',
                          'method_exchangeImplementations',
                          'vc.scaleRatio =', 'setStatusBarHidden:',
                          'bundleIdentifier','UIImagePNGRepresentation',
                          'accessibilityLabel'):
            self.assertNotIn(forbidden,fix)
        self.assertIn('ScarletIslandScheduleScrollContentRepair(window, root, target);',G)
        self.assertIn('ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);',G)
        self.assertEqual(G.count('ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);'),1)
        self.assertIn('for(NSNumber *delay in @[@650, @2600])',G)

    def test_receipt_survives_to_final_jsonl(self):
        for token in ('guest_local_owner_inset_receipt','guest_local_owner_inset_applied',
                      'guest_local_owner_inset_skipped','guest_root_after_pt',
                      'owner_groups','owner_dominant_controls','owner_frame_y',
                      'owner_safe_top'):
            self.assertIn(token,H)
        for token in ('"owner_groups"', '"owner_dominant_controls"',
                      '"owner_dominant_images"','"owner_frame_y"',
                      '"owner_safe_top"', '"reason"','"guest_root_after_pt"'):
            self.assertIn(token,R)

if __name__ == "__main__":
    unittest.main()
