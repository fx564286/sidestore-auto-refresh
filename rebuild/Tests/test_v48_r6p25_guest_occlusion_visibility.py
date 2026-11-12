"""R6P25: window-space unsafe y alone does not prove a drawn island overlap.

The clip-chain probe is read-only; app scale, scroll content offset, root inset,
keyboard and AVAudioSession behavior are intentionally unchanged.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
HOST = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()


def clipped_intersection(rect, clips):
    """Reference geometry contract: x1,y1,x2,y2; non-positive area is hidden."""
    x1, y1, x2, y2 = rect
    for a1, b1, a2, b2 in clips:
        x1, y1, x2, y2 = max(x1, a1), max(y1, b1), min(x2, a2), min(y2, b2)
        if x2 <= x1 or y2 <= y1:
            return None
    return x1, y1, x2, y2


def visible_below_safe_top(original, clips, safe_top=62):
    frame = clipped_intersection(original, clips)
    return frame is not None and frame[1] < safe_top - 2 and frame[3] > 5


class R6P25Visibility(unittest.TestCase):
    def test_clip_chain_separates_offscreen_from_visible_geometry(self):
        # Raw y=3 is a false island overlap when ancestor clips at y=100.
        self.assertFalse(visible_below_safe_top((2, 3, 45, 48),
                                                [(0, 100, 440, 900)]))
        # The same raw y=3 is a genuine visible unsafe region when clipped
        # parent starts at y=0 and content remains visible under 62pt.
        self.assertTrue(visible_below_safe_top((2, 3, 45, 48),
                                               [(0, 0, 440, 900)]))
        # Partial clip to y=70 eliminates visible content under the island.
        self.assertFalse(visible_below_safe_top((2, 3, 45, 100),
                                                [(0, 70, 440, 900)]))

    def test_actual_guest_probe_intersects_each_clipping_ancestor(self):
        fn = GUEST.split('static CGRect ScarletIslandVisibleFrameInWindow(', 1)[1]
        fn = fn.split('static void ScarletIslandWalkViews(', 1)[0]
        for token in ('CGRectIntersection(visible, window.bounds)',
                      'parent.clipsToBounds',
                      '[parent isKindOfClass:UIScrollView.class]',
                      'CGRectIntersection(visible, clip)',
                      'CGRectIsNull(visible)', 'CGRectIsEmpty(visible)'):
            self.assertIn(token, fn)
        self.assertNotIn('contentInset =', fn)
        self.assertNotIn('additionalSafeAreaInsets =', fn)
        self.assertNotIn('scaleRatio', fn)

    def test_visible_and_clipped_counts_relayed(self):
        for field in ('visible_unsafe_controls', 'clipped_unsafe_controls',
                      'visible_unsafe_images', 'clipped_unsafe_images'):
            self.assertIn('@"' + field + '"', GUEST)
            self.assertIn('"' + field + '"', HOST)
        for counter in ('visibleUnsafeControls', 'clippedUnsafeControls',
                        'visibleUnsafeImageNodes', 'clippedUnsafeImageNodes'):
            self.assertIn('metrics->' + counter + '++', GUEST)
        self.assertIn('metrics->unsafeControls++', GUEST)
        self.assertIn('metrics->unsafeImageNodes++', GUEST)
        self.assertIn('guest_content_geometry_probe', HOST)

    def test_no_global_gui_or_audio_keyboard_rewrite(self):
        helper = GUEST.split('static CGRect ScarletIslandVisibleFrameInWindow(', 1)[1]
        helper = helper.split('static void ScarletIslandWalkViews(', 1)[0]
        for forbidden in ('UIApplication.sharedApplication', 'endEditing',
                          'setActive:', 'setCategory:', 'scroll.contentOffset',
                          'window.frame ='):
            self.assertNotIn(forbidden, helper)
        self.assertIn('vc.scaleRatio = 1', HOST)


if __name__ == "__main__":
    unittest.main()
