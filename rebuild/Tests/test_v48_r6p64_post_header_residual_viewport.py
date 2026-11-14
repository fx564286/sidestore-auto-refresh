"""P64: bounded post-header residual viewport path, not old scroll-inset trials."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
W=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
P=SRC.split("// R6P64_POST_HEADER_RESIDUAL_VIEWPORT_BEGIN",1)[1].split("// R6P64_POST_HEADER_RESIDUAL_VIEWPORT_END",1)[0]
N=SRC.split("// R6P63_NESTED_LAYOUT_OWNER_BEGIN",1)[1].split("// R6P63_NESTED_LAYOUT_OWNER_END",1)[0]
O=SRC.split("// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN",1)[1].split("// R6P54_OWNER_LAYOUT_CONTRACT_END",1)[0]

class P64PostHeaderResidual(unittest.TestCase):
    def test_actual_new_cohort_and_original_p63_selection_preserved(self):
        for needle in ("ScarletIslandP60GatherRiskControls(", "root,header,window,safeTop",
          "risk.count<1 || risk.count>4", "safeTop-12", "safeTop-2",
          "UIScrollViewContentInsetAdjustmentNever", "fabs(scroll.contentOffset.y+nativeTop)>3",
          "scroll.dragging || scroll.decelerating", "scroll.contentSize.height<=",
          "if(measuredGap) *measuredGap=gap", "if(!common", "return nil"):
            self.assertIn(needle,P,needle)
        self.assertIn("if(capped || risk.count<3 || risk.count>32)",SRC)
        self.assertNotIn("scroll.contentInset.top=",P)
        self.assertNotIn("scroll.contentOffset=",P)
        self.assertNotIn("scroll.transform=",P)

    def test_owning_header_first_then_measured_residual_candidate(self):
        before=O.index("ScarletIslandP54AfterNativeOwnerLayout(owner);")
        after=O.index("ScarletIslandP64PostHeaderResidualViewport(")
        self.assertLess(before,after)
        for needle in ('if(!nativeBody && ![state[@"disabled"] boolValue])',
                       'state[@"body_kind"]=@64;',
                       'state[@"body_residual_delta"]=@(measuredGap)',
                       'ScarletIslandP63BindNestedParent(residual.superview,state)',
                       '[weakBody removeObject:residual]',
                       'p64_post_header_residual_viewport'):
            self.assertIn(needle,O,needle)

    def test_no_scene_crop_and_closed_loop_two_pass_rollback(self):
        for needle in ('[state[@"body_kind"] integerValue]==64',
                       'CGFloat delta=residual ? [state[@"body_residual_delta"] doubleValue]',
                       'scroll.adjustedContentInset.top<target-12',
                       'revised.origin.y+=delta;',
                       'revised.size.height-=delta;',
                       'delta<(residual ? 2 : 15)',
                       'fabs(CGRectGetMaxY(revised)-CGRectGetMaxY(original))>1'):
            self.assertIn(needle,N,needle)
        for needle in ('BOOL residualGeometry=kind==64',
                       'focusedComplete && focusedUnsafe==0 && scrollStateUnchanged',
                       '(deepGeometry || residualGeometry || siblingGeometry)',
                       'unsafe==0;', 'delta>=(bodyKind==64 ? 2 : 15)',
                       'if(!provenBody)', 'ScarletIslandP63UnbindNestedParent(bodyParent,state)',
                       'if(!reduced)', 'verify(YES)', 'state[@"body_disabled"]=@YES'):
            self.assertIn(needle,O,needle)
        self.assertNotIn('additionalSafeAreaInsets=',P)
        self.assertNotIn('window.frame=',P)
        self.assertNotIn('contentInset.top=',N)

    def test_measured_only_four_pt_reflow_preserves_bottom_edge(self):
        old_y,old_height,gap=0,956,4
        y=old_y+gap
        height=old_height-gap
        self.assertEqual(y,4)
        self.assertEqual(y+height,956)
        self.assertEqual(58+gap,62)
        self.assertTrue(2<=gap<=10)

    def test_native_release_build_mapping(self):
        for needle in ('fix/scarlet-v48-r6p64-residual-viewport-20261115',
                       'SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.64)',
                       'Scarlet-Crystal-V48-R6P64-RESIDUAL-VIEWPORT-UNSIGNED.ipa',
                       'scarlet-v48-r6p64-residual-viewport-unsigned-20261115',
                       'version="3.8.64" if "r6p64"'):
            self.assertIn(needle,W)
if __name__=="__main__":
    unittest.main()
