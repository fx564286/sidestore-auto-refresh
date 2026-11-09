"""V13 visible settings removed and current full-screen guest survives filtering."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
PATCH=(R/'integration/apply_scarlet_host.py').read_text()
GUEST=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
CAP=(R/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
MODULE=(R/'HostApp/ScarletFeatureModulesSection.swift').read_text()
class V13(unittest.TestCase):
 def test_multitask_settings_navigation_is_physically_removed(self):
  self.assertIn('source = source.replace(multitask_menu, "")',PATCH)
  self.assertIn('LCMultitaskSettingView()',PATCH)
  self.assertNotIn('.hidden()',PATCH)
 def test_running_fullscreen_guest_present_not_phantom_apps(self):
  self.assertIn('currentAppRow',GUEST)
  self.assertIn('SCARLET_GUEST_CURRENT_RUNNING',GUEST)
  self.assertIn('UserDefaults.standard.string(forKey: "selected")',GUEST)
  self.assertIn('bundleID == guestIdentifier',GUEST)
  self.assertIn('reloadApps: { installedApps(guestIdentifier: name) }',GUEST)
  self.assertIn('apps.filter { !$0.isCurrent }',GUEST)
 def test_compact_controls_preserve_function(self):
  self.assertNotIn('LabeledContent("LiveContainer 서명 인증서"',CAP)
  self.assertIn('LabeledContent("서명 상태"',CAP)
  self.assertIn('LabeledContent("자동 갱신"',CAP)
  self.assertIn('SideStore 인증서 받기',CAP)
  self.assertIn('P12 파일 선택',CAP)
  self.assertIn('Toggle("멀티탭 전환 애니메이션"',MODULE)
  self.assertIn('Toggle("멀티탭 진동 피드백"',MODULE)
