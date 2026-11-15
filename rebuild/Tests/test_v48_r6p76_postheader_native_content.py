"""P76 P75 signed device: severe y50 nodes survive P60 body rollback despite safe header."""
import unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
G=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
H=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
F=(R/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class PostHeaderContentOrigin(unittest.TestCase):
 def test_measured_post_header_cohort_only(self):
  p=G.split('// R6P76_POST_HEADER_SCOPED_SCROLL_CONTENT_ORIGIN_BEGIN',1)[1].split('// R6P76_POST_HEADER_SCOPED_SCROLL_CONTENT_ORIGIN_END',1)[0]
  for key in ('ScarletIslandP60GatherRiskControls(root,header,window,top,0',
    'risk.count<4 || risk.count>12','y<top-20 || y>=top-7',
    'fabs(scroll.contentOffset.y+nativeTop)>3',
    'CGRectGetHeight(frame)<CGRectGetHeight(window.bounds)*0.76',
    'scroll.tracking || scroll.decelerating',
    'fabs(nativeTop-scroll.contentInset.top)>2',
    'ScarletIslandP76UniqueResidualScroll('):
   self.assertIn(key,p,key)
  for banned in ('window.frame=', 'root.frame=', 'scroll.frame=',
    'setStatusBarHidden', 'scroll.transform=','contentSize='):
   self.assertNotIn(banned,p,banned)
 def test_same_native_content_inset_and_offset_delta(self):
  p=G.split('// R6P76_POST_HEADER_SCOPED_SCROLL_CONTENT_ORIGIN_BEGIN',1)[1].split('// R6P76_POST_HEADER_SCOPED_SCROLL_CONTENT_ORIGIN_END',1)[0]
  for key in ('applied.top+=shift',
    'scroll.contentInset=applied;',
    'scroll.contentOffset=CGPointMake(originalOffset.x,originalOffset.y-shift)',
    'sc.contentInset=originalInset;',
    'sc.contentOffset=CGPointMake(live.x,live.y+shift);',
    'CGRectEqualToRect(sc.frame,originalFrame)',
    'CGSizeEqualToSize(sc.contentSize,originalContent)',
    'remaining==0 && band.severeNodes==0',
    'state[@"p76_proven"]=@YES',
    'guest_owner_content_reflow_retained',
    'guest_owner_content_reflow_reverted'):
   self.assertIn(key,p,key)
 def test_runs_only_after_native_header_retained_and_pre_p74_probes(self):
  self.assertIn('if(reduced && late) {',G)
  self.assertIn('ScarletIslandP76TryPostHeaderContentOrigin(w,vc,safeTop);',G)
  self.assertIn('for(NSNumber *late in @[@2850, @3550])',G)
  self.assertIn('for(NSNumber *delay in @[@650, @2600])',G)
  self.assertIn('let noNear = near == 0',H)
  self.assertIn('(noNear || nearBoundary)',H)
  self.assertIn('headerVerified && complete && severe == 0',H)
  self.assertIn('guard nativeStatusBandFirstPassPIDs.remove(pid)',H)
 def test_actual_signed_host_bundle_path_fallback_not_guest_bundle_main(self):
  a=F.split('private func verifiedHostBundleURL()',1)[1].split('private func performRegistration()',1)[0]
  for key in ('Bundle(for: ScarletGuestRefreshAgent.self)',
    'ProcessInfo.processInfo.arguments.first',
    'directory.lastPathComponent == "LiveProcess.appex"',
    'directory.deletingLastPathComponent().lastPathComponent == "PlugIns"',
    'hostURL.pathExtension == "app"'):
   self.assertIn(key,a)
  self.assertNotIn('Bundle.main',a)
  self.assertIn('guard let hostURL = verifiedHostBundleURL()',F)
  self.assertIn('"host_selected_team_mismatch"',F)
 def test_p76_ci_release(self):
  for x in ('fix/scarlet-v48-r6p76-postheader-scroll-20261115',
    '--host-build-version 3.8.76','"r6p76"',
    'Scarlet-Crystal-V48-R6P76-NATIVE-CONTENT-UNSIGNED.ipa',
    'scarlet-v48-r6p76-native-content-unsigned-20261115'):
   self.assertIn(x,W,x)
if __name__=='__main__':unittest.main()
