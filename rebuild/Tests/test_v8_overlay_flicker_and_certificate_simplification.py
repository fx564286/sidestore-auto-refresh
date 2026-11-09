"""V8 regressions against the V7 same-size orientation flicker."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
OVERLAY=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
PANEL=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
class V8Contracts(unittest.TestCase):
    def test_no_alpha_zero_when_scene_geometry_unchanged(self):
        method=OVERLAY.split('private static func settleOverlayAfterRotation() {')[1].split('    // Use the host')[0]
        self.assertIn('guard rotationWatchTask == nil else { return }',method)
        self.assertIn('lastStableSceneSize',method)
        self.assertIn('if abs(current.width - baseline.width) > 1 ||',method)
        self.assertIn('if !geometryChanged {',method)
        self.assertLess(method.index('if !geometryChanged {'),method.index('overlay.alpha = 0'))
        self.assertIn('guard geometryChanged',method)
        self.assertIn('rotationWatchTask?.cancel()',OVERLAY)
        self.assertIn('if rotationGeneration == token { rotationWatchTask = nil }',method)
        self.assertNotIn('floatingWindow.alpha = 0',method)
    def test_one_certificate_button_fallback_and_manual_foldout(self):
        self.assertIn('Label("SideStore 인증서 받기"',PANEL)
        self.assertEqual(PANEL.count('Label("SideStore 인증서 받기"'),1)
        self.assertNotIn('DisclosureGroup(isExpanded: $isAdvancedCertificateExpanded)',PANEL)
        self.assertIn('Label("P12 파일 선택"',PANEL)
        self.assertIn('retrieveSideInstallerStyleCertificate()',PANEL)
        self.assertNotIn('Label("SideInstaller 방식 · SideStore 인증서 가져오기"',PANEL)
        self.assertIn('hostTeam == archiveTeam',PANEL)
        self.assertIn('isConfirmingCertReplacement',PANEL)
        self.assertIn('replacement_readback_failed',PANEL)
if __name__=='__main__':unittest.main()
