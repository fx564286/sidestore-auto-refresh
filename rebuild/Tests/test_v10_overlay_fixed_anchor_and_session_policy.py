"""V10 regression: fixed round-tab point, exact-only hit-test and safe guest state."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
GUEST=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
CERT=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
UPSTREAM=GUEST
class V10Contract(unittest.TestCase):
    def test_overlay_frame_never_resized_on_toggle(self):
        method=GUEST.split('private static func resizeOverlay(open: Bool, appCount: Int) {')[1].split('    // UIDevice.orientationDidChangeNotification')[0]
        self.assertNotIn('floating.frame =',method)
        self.assertNotIn('floatingWindow.frame =',method)
        self.assertIn('floating.isExpanded = open',method)
        self.assertIn('floating.panelRect = panelFrame(in: floating)',method)
        self.assertIn('button_center_unchanged',method)
    def test_button_stays_at_absolute_screen_position(self):
        self.assertIn('initialButtonCenter: center(in: original)',GUEST)
        self.assertIn('.position(x: screenButtonCenter.x, y: screenButtonCenter.y)',GUEST)
        self.assertIn('screenButtonCenter = CGPoint(x: x, y: y)',GUEST)
        self.assertIn('let next = frame(in: guestWindow)',GUEST)
        self.assertIn('overlay.frame = frame(in: original)',GUEST)
        self.assertIn('overlay.layer.masksToBounds = false',GUEST)
        self.assertIn('lastStableSceneSize',GUEST)
        self.assertNotIn('width = open ? min(430',GUEST)
    def test_full_screen_nonkey_overlay_passes_unrelated_touches(self):
        self.assertIn('return isExpanded && panelRect.contains(point)',GUEST)
        self.assertIn('hypot(point.x - buttonCenter.x',GUEST)
        self.assertIn('return super.point(inside: point, with: event)',GUEST)
        self.assertIn('overlay.windowLevel = UIWindow.Level.alert + 1',GUEST)
        self.assertNotIn('original.frame =',GUEST)
        self.assertNotIn('host.frame =',GUEST)
    def test_native_existing_session_before_host_relaunch(self):
        self.assertIn('MultitaskManager.isUsing(container: container)',GUEST)
        self.assertIn('MultitaskWindowManager.openExistingAppWindow(dataUUID: container)',GUEST)
        self.assertIn('MultitaskDockManager.shared.bringMultitaskViewToFront(uuid: container)',GUEST)
        self.assertLess(GUEST.index('switch_existing_multitask_session'),
                        GUEST.index('let success = LCSharedUtils.launchToGuestApp'))
        self.assertIn('switch_requires_relaunch',GUEST)
        self.assertIn('existing',GUEST)
        self.assertNotIn('removeItem(at:',GUEST)
    def test_only_two_jitless_certificate_buttons(self):
        body=CERT.split('    var body: some View {',1)[1]
        self.assertIn('Label("SideStore 인증서 받기"',body)
        self.assertIn('Label("P12 파일 선택"',body)
        self.assertNotIn('DisclosureGroup(',body)
        self.assertNotIn('Button(action: requestManualRefresh)',body)
        self.assertNotIn('Label("JIT-Less 모드 진단"',body)
        self.assertIn('isConfirmingCertReplacement',CERT)
        self.assertIn('replacement_readback_failed',CERT)
if __name__=='__main__':unittest.main()
