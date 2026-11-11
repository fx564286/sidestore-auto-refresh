"""R5W regression: force outside tap delivery to owner *normal* UIWindow and fix guest bootstrap gating.
These are source tests, not physical iPhone interaction verification.
"""
from pathlib import Path
import hashlib,unittest
ROOT=Path(__file__).resolve().parents[1]
SW=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
TRACE=(ROOT/'HostApp/ScarletGuestSessionLedger.swift').read_text()
INTEGRATE=(ROOT/'integration/apply_scarlet_host.py').read_text()
FLOW=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class R5WCorrectOwners(unittest.TestCase):
 def test_window_outside_not_overlay_hit(self):
  self.assertIn('private final class ScarletSwitcherHostOutsideShield: UIControl',SW)
  self.assertIn('weak var touchHostWindow: UIWindow?',SW)
  self.assertIn('host.addSubview(created)',SW)
  self.assertIn('host.bringSubviewToFront(shield)',SW)
  self.assertIn('host_outside_shield_tapped',SW)
  self.assertIn('dismissState?.requestClose()',SW)
  self.assertIn('return panelRect.insetBy(dx: -3, dy: -3).contains(point)',SW)
  self.assertIn('if isExpanded && !panelRect.insetBy(dx: -3, dy: -3).contains(point)',SW)
  self.assertIn('host_outside_shield_removed',SW)
  self.assertIn('overlay.touchHostWindow = original',SW)
  self.assertIn('overlay.touchHostWindow = host',SW)
  self.assertIn('floating.panelRect = panelFrame(in: floating)\n        floating.isExpanded = open',SW)
 def test_original_v48_pan_unmodified(self):
  c=SW[SW.index('// UIkit pan tracks finger'):SW.index('@objc(ScarletFullscreenGuestTabInstaller)')]
  p=SW[SW.index('    private static func panChanged('):SW.index('    private static func resizeOverlay(')]
  self.assertEqual(hashlib.sha256(c.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
  self.assertEqual(hashlib.sha256(p.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
 def test_full_guest_hook_is_not_wrongly_gated_on_liveprocess(self):
  self.assertIn('if(!NSUserDefaults.lcGuestAppId || ![NSThread isMainThread]) return original;',INTEGRATE)
  self.assertIn('safearea_root_pilot_disabled',INTEGRATE)
  self.assertIn('static void ScarletGuestInstallRootSafeAreaObserver(void);',INTEGRATE)
  self.assertIn('safearea_root_ready_after_window',TRACE)
  self.assertIn('safearea_root_window_timeout',TRACE)
  self.assertIn('safearea_root_adjusted',TRACE)
  self.assertIn('safearea_root_getter_installed',TRACE)
 def test_release(self):
  self.assertIn('scarlet-v48-r5w-unsigned-20261111',FLOW)
  self.assertIn('Scarlet-Crystal-V48-R5W-UNSIGNED.ipa',FLOW)
if __name__=='__main__':unittest.main()
