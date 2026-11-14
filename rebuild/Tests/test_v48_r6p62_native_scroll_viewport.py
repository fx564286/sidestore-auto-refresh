"""P62: accept finite, natively-scrollable content that fits the original window."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
G=(R/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
W=(R.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
P=G.split("// R6P60_COMMON_SCROLL_ANCESTOR_BEGIN",1)[1].split("// R6P60_COMMON_SCROLL_ANCESTOR_END",1)[0]
O=G.split("// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN",1)[1].split("// R6P54_OWNER_LAYOUT_CONTRACT_END",1)[0]
class P62Viewport(unittest.TestCase):
    def test_old_extra_content_requirement_is_replaced_with_post_docking_reachability(self):
        self.assertNotIn("scroll.contentSize.height<h+safeTop+25",P)
        self.assertNotIn("CGRectGetHeight(originalBody)+delta+20",O)
        for item in ("scroll.contentSize.height<=0","isfinite(scroll.contentSize.height)",
                     "scroll.scrollEnabled","if(node!=scroll && ![node isDescendantOfView:scroll])"):
            self.assertIn(item,P)
        for item in ("BOOL canReachBottom=isfinite(content)","content<=CGRectGetHeight(revised)+2",
                     "content>CGRectGetHeight(revised)", "scroll.scrollEnabled && canReachBottom",
                     "revised.size.height>=CGRectGetHeight(window.bounds)*0.65"):
            self.assertIn(item,O)
    def test_no_destruction_or_global_resize_and_requires_two_pass_zero_risk(self):
        for item in ("scrollStateUnchanged", "focusedComplete && focusedUnsafe==0",
                     "body_reflow_passes", "guest_owner_content_reflow_retained",
                     "guest_owner_content_reflow_reverted","feed.frame=oldFeed"):
            self.assertIn(item,O)
        for bad in ("window.frame=", "root.frame=", "scroll.contentInset=",
                    "scroll.contentOffset=", "scroll.contentSize="):
            self.assertNotIn(bad,P+O)
    def test_native_CI_build_and_release_version(self):
        for x in ("fix/scarlet-v48-r6p62-scroll-viewport-20261114",
                  "SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.62)",
                  "scarlet-v48-r6p62-scroll-viewport-unsigned-20261114",
                  "Scarlet-Crystal-V48-R6P62-SCROLL-VIEWPORT-UNSIGNED.ipa",
                  'version="3.8.62" if "r6p62"'):
            self.assertIn(x,W)
if __name__=="__main__":unittest.main()
