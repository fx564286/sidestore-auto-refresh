"""Never conflate SideStore device installation with LiveContainer guest import."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
HOME=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
class DualInstallRoutes(unittest.TestCase):
    def test_both_install_routes_share_home_with_equal_layout(self):
        self.assertEqual(HOME.count('installPathRow("'),2)
        self.assertIn('"SideStore 앱 설치"',HOME)
        self.assertIn('"게스트 앱 설치"',HOME)
        self.assertIn("onAction(.serviceInstallIPA)",HOME)
        self.assertIn("onAction(.localImportGuestIPA)",HOME)
        self.assertIn("SCARLET_HOME_DEVICE_IPA_INSTALL",HOME)
        self.assertIn("SCARLET_HOME_GUEST_IPA_INSTALL",HOME)
        self.assertNotIn('engineEntry("SideStore"',HOME)
        self.assertNotIn('"최근 앱"',HOME)
        self.assertNotIn('"빠른 작업"',HOME)
    def test_original_guest_import_and_no_sidestore_window(self):
        self.assertIn("LCAppListView()",HOST)
        self.assertIn("case .localImportGuestIPA:",HOST)
        self.assertIn("case .serviceInstallIPA:",HOST)
        self.assertNotIn("LCUtils.openSideStore(",HOST)
        self.assertIn("prepareDeviceIPAInstall()",HOST)
        self.assertIn("아직 검증되지 않았습니다",HOST)
        self.assertIn("UserDefaults.sideStoreExist()",HOST)
if __name__=="__main__":
    unittest.main()
