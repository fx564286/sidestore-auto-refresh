"""Never conflate SideStore device installation with LiveContainer guest import."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
HOME=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
class DualInstallRoutes(unittest.TestCase):
    def test_one_title_menu_with_two_distinct_install_routes(self):
        self.assertEqual(HOME.count("Menu {"),1)
        self.assertIn('Label("IPA 설치하기"',HOME)
        self.assertIn('Label("게스트 앱 설치하기"',HOME)
        self.assertIn("onAction(.serviceInstallIPA)",HOME)
        self.assertIn("onAction(.localImportGuestIPA)",HOME)
        self.assertIn("SCARLET_INSTALL_CHOICE_DEVICE_IPA",HOME)
        self.assertIn("SCARLET_INSTALL_CHOICE_GUEST_APP",HOME)
        self.assertEqual(HOME.count("onAction(.serviceInstallIPA)"),1)
        self.assertEqual(HOME.count("onAction(.localImportGuestIPA)"),1)
        self.assertNotIn('installPathRow(',UI)
        self.assertNotIn('engineEntry("SideStore"',HOME)
        self.assertNotIn('"최근 앱"',HOME)
        self.assertNotIn('"빠른 작업"',HOME)
    def test_original_guest_import_and_no_sidestore_window(self):
        self.assertIn("LCAppListView(scarletStartIPAImport: guestIPAImportFromAddMenu)",HOST)
        self.assertIn("case .localImportGuestIPA:",HOST)
        self.assertIn("case .serviceInstallIPA:",HOST)
        self.assertNotIn("LCUtils.openSideStore(",HOST)
        self.assertIn("prepareDeviceIPAInstall()",HOST)
        self.assertIn("아직 검증되지 않았습니다",HOST)
        self.assertIn("UserDefaults.sideStoreExist()",HOST)
        self.assertIn("guestIPAImportFromAddMenu = true",HOST)
if __name__=="__main__":
    unittest.main()
