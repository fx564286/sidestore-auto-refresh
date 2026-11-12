"""R6P27: observe the closest scroll owner of actually visible unsafe nodes.

The R6P26 iPhone run showed 8 visible controls and 7 visible images in
scroll descendants while R6P22 classifier had zero eligible scrollers.
This does not authorize a blind contentInset or window/safe-area change.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = (ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
FIELDS = {
    "owner_groups", "owner_dominant_controls", "owner_dominant_images",
    "owner_tie", "owner_frame_y", "owner_frame_width_pct",
    "owner_frame_height_pct", "owner_adjusted_inset_top",
    "owner_content_inset_top", "owner_offset_y",
    "owner_adjustment_behavior", "owner_nested_scrolls",
    "owner_scroll_enabled", "owner_content_height_pct", "owner_safe_top",
}

class OwnerAttribution(unittest.TestCase):
    def test_all_anon_owner_metrics_survive_guest_to_jsonl(self):
        relay = H.split('if result == "guest_content_geometry_probe" {', 1)[1]
        relay = relay.split('let numericFields = [', 1)[1].split(']', 1)[0]
        recorder = R.split('private static let allowedFields: Set<String> = [',1)[1].split(']',1)[0]
        relay_fields = set(re.findall(r'"([a-z_]+)"', relay))
        allowed = set(re.findall(r'"([a-z_]+)"', recorder))
        self.assertTrue(FIELDS.issubset(relay_fields))
        self.assertTrue(FIELDS.issubset(allowed))
        for field in FIELDS:
            self.assertIn('@"'+field+'"', G)

    def test_only_visibly_unsafe_scroll_ancestors_are_counted(self):
        scanner = G.split('static void ScarletIslandWalkViews(', 1)[1].split(
            'static void ScarletIslandContentProbe(', 1)[0]
        self.assertEqual(scanner.count('ScarletIslandRecordVisibleScrollOwner('),2)
        self.assertIn('ScarletIslandVisibleFrameInWindow(view, window)',scanner)
        self.assertIn('metrics->visibleUnsafeControls++',scanner)
        self.assertIn('metrics->visibleUnsafeImageNodes++',scanner)
        owner = G.split('static void ScarletIslandRecordVisibleScrollOwner(',1)[1].split(
            'static void ScarletIslandWalkViews(',1)[0]
        for item in ('node.superview', 'isKindOfClass:UIScrollView.class',
                     'if(!owner) return;', 'if(owners.count >= 16) return;',
                     'dominant.contentInsetAdjustmentBehavior',
                     'dominant.adjustedContentInset.top'):
            self.assertIn(item, owner)
        for mutation in ('contentInset =', 'additionalSafeAreaInsets =',
                         'setFrame:', 'window.frame =', 'endEditing:',
                         'setActive:', 'scroll.contentOffset ='):
            self.assertNotIn(mutation, owner)

    def test_original_scroll_target_repair_is_not_expanded(self):
        self.assertIn('if(candidates.count != 1)',G)
        self.assertIn('scroll.contentInset = inset;',G)
        self.assertIn('if(depth > 24)',G)
        self.assertIn('return hops >= 64 ? CGRectNull : visible;',G)

if __name__ == '__main__':
    unittest.main()
