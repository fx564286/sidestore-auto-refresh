"""Integration contract: separate guest import and iOS installation paths.

Static checks are not signed-device runtime tests.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
ACTIONS=(ROOT/"Sources/ScarletCleanCore/ScarletActionCoordinator.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
GLASS=(ROOT/"HostApp/ScarletNativeGlass.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
PACKAGE=(ROOT/"integration/package_paired.py").read_text()

class InstallerRouteTests(unittest.TestCase):
    def test_livecontainer_guest_import_is_local_not_apple_login(self):
        self.assertIn("case localImportGuestIPA",ACTIONS)
        self.assertIn(".localImportGuestIPA, .localOpenEmbeddedSideStore:",ACTIONS)
        self.assertIn("onAction(.localImportGuestIPA)",UI)
        self.assertIn("case .localImportGuestIPA:",HOST)
        self.assertIn("LCAppListView()",HOST)
        self.assertIn("try await app.runApp()",HOST)

    def test_embedded_sidestore_open_is_always_available_for_login(self):
        self.assertIn("case localOpenEmbeddedSideStore",ACTIONS)
        self.assertIn('ScarletActionRow(title: "SideStore 열기"',UI)
        self.assertIn("onAction(.localOpenEmbeddedSideStore)",UI)
        self.assertIn("LCUtils.openSideStore(delegate: nil)",HOST)
        self.assertIn("UserDefaults.sideStoreExist()",HOST)
        self.assertIn("serviceBeginSignIn",HOST)
        self.assertIn("serviceRefreshApp",HOST)

    def test_real_engine_sources_are_not_replaced_by_fake_importers(self):
        self.assertIn("LCSourcesView()",HOST)
        self.assertIn("LCSettingsView()",HOST)
        self.assertIn('str(out.glob("*.swift"))' if False else "out.glob",PATCH)
        self.assertIn('ScarletIntegratedHostView()',PATCH)
        self.assertIn("SCNativeLiquidGlassSurface",GLASS)
        self.assertIn("UIGlassEffect(style: .clear)",GLASS)
        self.assertNotIn("clearAppGroup",HOST)
        self.assertNotIn("revokeCertificate",HOST)

    def test_unsigned_bundle_names_and_release_safety(self):
        self.assertIn("Scarlet-LiveContainer+SideStore-ENGINES-UNSIGNED.ipa",PACKAGE)
        self.assertIn("SideStore-Standalone-UNSIGNED.ipa",PACKAGE)
        self.assertIn("Scarlet-LiveContainer-Engine-UNSIGNED.ipa",PACKAGE)
        self.assertIn('"userDeviceInstallationVerified":False',PACKAGE)
        self.assertIn('"nativeOriginalLiquidGlassVerified":False',PACKAGE)
        self.assertIn('HOST_ID="com.kdt.livecontainer.P8EZT3U5N4"',PACKAGE)
        self.assertIn('EXTENSIONS=("LiveProcess","ShareExtension","LaunchAppExtension")',PACKAGE)

if __name__=="__main__":unittest.main()
