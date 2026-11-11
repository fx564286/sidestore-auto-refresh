"""R5V contracts: route outside hits from remote guest UIApplication to host.
Unit assertions are not evidence of iPhone optical/interaction success.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
TAB=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
G=(R/'integration/apply_scarlet_host.py').read_text()
LEDGER=(R/'HostApp/ScarletGuestSessionLedger.swift').read_text()
FLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class RemoteGuestOutsideEvents(unittest.TestCase):
 def test_guest_application_not_host_window_is_owner(self):
  for v in ('@selector(sendEvent:)', '@selector(hook_scarletGuestSendEvent:)',
        'ScarletGuestHandleOutsideEvent(UIEvent *event)',
        'if(touch.phase != UITouchPhaseEnded || touch.tapCount == 0)',
        'CFNotificationCenterPostNotification(CFNotificationCenterGetDarwinNotifyCenter()',
        'guest_outside_touch_forwarded'):
   self.assertIn(v,G)
  self.assertIn('"guest_outside_touch_forwarded"',LEDGER)
 def test_host_receives_and_closes_original_panel(self):
  for v in ('ScarletGuestOutsideDarwinBridge',
        'CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter()',
        'ScarletGuestOutsideDarwinReceived',
        'guest_process_outside_tap_received',
        'Scarlet.Pilot.Switcher.Expanded.V1',
        'shared.synchronize()',
        'closePanel()'):
   self.assertIn(v,TAB)
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',TAB)
  self.assertIn('private static func panChanged(',TAB)
  self.assertIn('if isExpanded && !panelRect.insetBy(dx: -3, dy: -3).contains(point)',TAB)
 def test_guest_safe_not_hard_gated_on_absent_pilot_shared_bool(self):
  self.assertIn('safearea_root_local_measurement',G)
  self.assertIn('ScarletGuestInstallRootSafeAreaGetter();',G)
  self.assertIn('CGRectGetMaxY(window.windowScene.statusBarManager.statusBarFrame)',G)
  self.assertIn('ScarletGuestInstallRootSafeAreaObserver();',G)
  self.assertIn('"safearea_root_local_measurement"',LEDGER)
 def test_tagged_release(self):
  self.assertIn('scarlet-v48-r5v-unsigned-20261111',FLOW)
  self.assertIn('Scarlet-Crystal-V48-R5V-UNSIGNED.ipa',FLOW)
if __name__=='__main__': unittest.main()
