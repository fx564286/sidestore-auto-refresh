"""P43 P42-device proof: exact remote slot rather than local UIWindow; native guest tone."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GUEST=(ROOT/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
REC=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
WF=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class NativeChromeP43(unittest.TestCase):
 def test_host_verifies_exact_pid_and_real_fbscene_not_provisional_window(self):
  helper=HOST.split('private func verifyNativeChromeRemoteSlot(',1)[1].split('private func chromeTop(',1)[0]
  for term in ('vc.contentView?.bounds.height ?? -1',
    'vc.scarletNativeTransparentChromeSlot',
    'self.chromeEligiblePIDs.contains(vc.pid)',
    'self.chromeTop(in: realScene) > 0',
    'abs(rect.minY - expected.minY) < 2',
    'abs(rect.height - expected.height) < 2',
    'abs(content - expected.height) < 2',
    'self.chromeVerifiedPIDs.insert(vc.pid)',
    'self.publishNativeChromeVerifiedPIDs(realScene)',
    'attempt < 4',
    'guest_chrome_remote_slot_verified',
    'guest_chrome_remote_slot_unverified'):
   self.assertIn(term,helper,term)
 def test_native_chrome_guest_reentry_accepts_host_proof_with_strict_pid(self):
  portion=GUEST.split('NSArray *verifiedPIDs =',1)[1].split('if(!isfinite(target)',1)[0]
  for term in ('TransparentChromeVerifiedPIDs.V1','nativeOwner &&',
        '[verifiedPIDs containsObject:@(getpid())]',
        'frameConfirmed || confirmedEarlier ||',
        'hostRemoteVerified','&scarletIslandConfirmedChromeWindowKey',
        'guest_transparent_chrome_host_verified',
        'own.doubleValue','root.additionalSafeAreaInsets=extra'):
   self.assertIn(term,portion,term)
  self.assertIn('TransparentChromeVerifiedPIDs.V1',HOST)
  self.assertIn('chromeVerifiedPIDs.remove(old.pid)',HOST)
 def test_surface_classifier_reads_background_only_not_images_or_text(self):
  body=GUEST.split('// R6P43_GUEST_TONE_BEGIN',1)[1].split(
      '// R6P43_GUEST_TONE_END',1)[0]
  for term in ('CGRectContainsPoint(view.bounds,local)',
        'view.backgroundColor',
        'resolvedColorWithTraitCollection:',
        'getRed:&red green:&green blue:&blue alpha:&alpha',
        'luminance>=0.83','luminance<=0.17',
        'surface_tone', 'ScarletIslandRepeatSurfaceToneCheck',
        'scarletIslandSurfaceToneMonitorKey','900*NSEC_PER_MSEC'):
   self.assertIn(term,body,term)
  for prohibited in ('drawHierarchy','snapshotView','renderInContext',
         'accessibilityLabel','bundleIdentifier','UIImagePNGRepresentation',
         'NSStringFromClass','screenCapture','window.snapshot','textContent'):
   self.assertNotIn(prohibited,body,prohibited)
 def test_host_consumes_native_tone_instead_of_dark_trait_or_app_identity(self):
  func=HOST.split('private func applyNativeChromeAppearance(',1)[1].split(
       'private func chromeTop(',1)[0]
  for term in ('let tone = chromeSurfaceToneByPID[guest.pid] ?? 0',
      'tone == 1 || tone == 2',
      'guest_chrome_appearance_unresolved',
      'let isLight = tone == 1',
      'guest_chrome_appearance_applied',
      'chromeStatusBarPreference = isLight ? .darkContent : .lightContent',
      'private func onGuestSurfaceTone('):
   self.assertIn(term,func,term)
  self.assertNotIn('traitCollection.userInterfaceStyle',func)
  self.assertIn('onSurfaceToneMeasured?(pid, tone)',HOST)
  self.assertIn('guest_chrome_surface_tone',HOST)
 def test_other_guest_keeps_full_scene_and_old_mutators_are_quarantined(self):
  body=HOST.split('private func updateNativeChromeSlots(',1)[1].split('private func onUnsafeGuestControls(',1)[0]
  self.assertIn('let reserved = vc.pid > 0 && chromeEligiblePIDs.contains(vc.pid)',body)
  self.assertIn('contentSlot(in: scene, reserved: reserved)',body)
  self.assertIn('applyNativeChromeAppearance(for: guest, scene: scene)',body)
  self.assertIn('chromeVerifiedPIDs.remove(vc.pid)',body)
  self.assertNotIn('view.window?.frame=',body)
  self.assertNotIn('scaleRatio=',body)
  p38=GUEST.split('// R6P38_LAYOUT_OWNER_BEGIN',1)[1].split(
       '// R6P38_LAYOUT_OWNER_END',1)[0]
  self.assertNotIn('    ScarletIslandTryMeasuredHeaderConstraintBridge(',p38)
 def test_diagnostic_contract_and_distinct_release(self):
  self.assertIn('"surface_tone"',REC)
  self.assertIn('guest_chrome_remote_slot_verified',HOST)
  self.assertIn('guest_chrome_remote_slot_unverified',HOST)
  self.assertIn('scarlet-v48-r6p43-host-verified-unsigned-20261113',WF)
  self.assertIn('Scarlet-Crystal-V48-R6P43-HOST-VERIFIED-UNSIGNED.ipa',WF)
if __name__=="__main__":unittest.main()
