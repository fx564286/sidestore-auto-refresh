"""P62: P61 signed native device disproved P60 original-height contentSize requirement."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
G=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
P62=G.split('// R6P62_MEASURED_SHORT_CONTENT_VIEWPORT_BEGIN',1)[1].split('// R6P62_MEASURED_SHORT_CONTENT_VIEWPORT_END',1)[0]
P60=G.split('// R6P60_COMMON_SCROLL_ANCESTOR_BEGIN',1)[1].split('// R6P60_COMMON_SCROLL_ANCESTOR_END',1)[0]
OWNER=G.split('// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN',1)[1].split('// R6P54_OWNER_LAYOUT_CONTRACT_END',1)[0]
class P62NativeViewport(unittest.TestCase):
    def test_gate_accepts_short_but_meaningful_scroll_extent(self):
        self.assertIn('projectedHeight=originalHeight-topReduction',P62)
        self.assertIn('contentHeight<projectedHeight*0.50',P62)
        self.assertNotIn('originalHeight+topReduction',P62)
        self.assertNotIn('scroll.contentSize.height<h+safeTop+25',P60)
        self.assertNotIn('CGRectGetHeight(originalBody)+delta+20',OWNER)
        self.assertIn('scroll,h,safeTop+CGRectGetHeight(header.bounds)',P60)
        self.assertIn('scroll,CGRectGetHeight(originalBody),delta',OWNER)
    def test_no_unguarded_geometry_mutation_or_inset_change(self):
        for x in ('scroll.scrollEnabled','topReduction<15','topReduction>190',
                  'projectedHeight<originalHeight*0.65',
                  '!isfinite(contentHeight)','!isfinite(offset.y)',
                  '!isfinite(insets.top)','!isfinite(insets.bottom)'):
            self.assertIn(x,P62,x)
        for forbidden in ('contentOffset=', 'contentInset=', 'setContentOffset:',
                          'root.frame=', 'window.frame=','method_exchangeImplementations'):
            self.assertNotIn(forbidden,P62)
        self.assertIn('revised.origin.y+=delta;',OWNER)
        self.assertIn('revised.size.height-=delta;',OWNER)
        self.assertIn('fabs(CGRectGetMaxY(revised)-CGRectGetMaxY(originalBody))<1',OWNER)
    def test_original_p60_native_rollback_and_two_sample_proof_remain(self):
        for x in ('if(!provenBody)', 'feed.frame=oldFeed;',
                  'state[@"body_disabled"]=@YES;',
                  'focusedComplete && focusedUnsafe==0 && scrollStateUnchanged',
                  'CGSizeEqualToSize(sc.contentSize',
                  'CGPointEqualToPoint(sc.contentOffset',
                  'UIEdgeInsetsEqualToEdgeInsets(sc.contentInset',
                  'guest_owner_content_reflow_retained',
                  'guest_owner_content_reflow_reverted'):
            self.assertIn(x,OWNER,x)
        self.assertIn('p62_measured_short_content_native_scroll_owner',OWNER)
    def test_release_identity_and_old_version_are_unchanged(self):
        self.assertIn('fix/scarlet-v48-r6p62-measured-content-scroll-20261114',W)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.62)',W)
        self.assertIn('Scarlet-Crystal-V48-R6P62-MEASURED-SCROLL-UNSIGNED.ipa',W)
if __name__=='__main__': unittest.main()
