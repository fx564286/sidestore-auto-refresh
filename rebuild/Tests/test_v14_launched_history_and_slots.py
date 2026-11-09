"""V14: a->Home->b history, real resident scene switching and released slot."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile

R=Path(__file__).resolve().parents[1]
G=(R/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
H=(R/"HostApp/ScarletIntegratedHostView.swift").read_text()
L=(R/"HostApp/ScarletGuestSessionLedger.swift").read_text()
PACKAGE=(R/"integration/package_paired.py").read_text()
VERIFY=(R/"integration/verify_engines.py").read_text()
AUD=(R/"scripts/audit_appid_footprint.py").read_text()

class V14(unittest.TestCase):
    def test_run_history_added_only_after_real_original_launch(self):
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(',H)
        self.assertIn('try await app.runApp(multitask: true)',H)
        self.assertIn('UIApplication.shared.supportsMultipleScenes',H)
        self.assertIn('MultitaskMode.nativeWindow.rawValue',H)
        self.assertIn('legacy_fullscreen_launch_requested',H)
        self.assertIn('ScarletGuestSessionLedger.remove(folder: folder)',H)
        self.assertIn('Scarlet.Guest.RecentSessions.V14',L)
        self.assertIn('LCUtils.appGroupUserDefault',L)
        self.assertIn('recent().filter { $0.folder != folder }',L)
        native=(R/"HostApp/ScarletGuestSwitcherOverlay.swift").read_text()
        self.assertIn('ScarletGuestSessionLedger.recent()',native)
        self.assertIn('entry.dataUUID ?? entry.folder',native)
        self.assertIn('openWindow(id: "Main")',native)
        self.assertIn('guard item.isLive else',native)

    def test_history_and_live_process_distinct(self):
        self.assertIn('recentFolders.contains(folder)',G)
        self.assertIn('apps.filter { !$0.isCurrent }',G)
        self.assertIn('app.canSwitch ? "실행 중 · 작업 유지"',G)
        self.assertIn('app.canRelaunch ? "최근 실행 · 누르면 다시 열기"',G)
        self.assertIn('MultitaskManager.isUsing(container:',G)
        self.assertIn('MultitaskWindowManager.openExistingAppWindow(',G)
        self.assertIn('switch_requires_relaunch',G)
        self.assertIn('SCARLET_GUEST_CURRENT_RUNNING',G)
        self.assertNotIn('apps.filter { !$0.isCurrent && $0.canSwitch }',G)

    def test_no_unapproved_new_app_ids(self):
        self.assertIn('RELEASE_EXTENSIONS=EXTENSIONS',PACKAGE)
        self.assertIn('LaunchAppExtension relies on the original ShareExtension',PACKAGE)
        self.assertIn('systemShareSheetImportAvailable',PACKAGE)
        self.assertIn('RELEASE_EXTENSIONS=EXTENSIONS',VERIFY)
        self.assertIn('Launch App shortcut requires ShareExtension',VERIFY)
        self.assertIn('"ShareExtension": HOST_ID + ".ShareExtension"',AUD)

    def test_strict_package_audit_three_ids(self):
        spec=importlib.util.spec_from_file_location("appid_v14",R/"scripts/audit_appid_footprint.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        host=module.HOST_ID
        def info(id,point):
            return plistlib.dumps({"CFBundleIdentifier":id,
                "NSExtension":{"NSExtensionPointIdentifier":point},
                "EXAppExtensionAttributes":{"EXExtensionPointIdentifier":point}})
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.ipa"
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("Payload/LiveContainer.app/Info.plist",
                           plistlib.dumps({"CFBundleIdentifier":host}))
                z.writestr("Payload/LiveContainer.app/PlugIns/LiveProcess.appex/Info.plist",
                           info(host+".LiveProcess","com.apple.extensionkit-service"))
                z.writestr("Payload/LiveContainer.app/PlugIns/LaunchAppExtension.appex/Info.plist",
                           info(host+".LaunchAppExtension","com.apple.appintents-extension"))
            with self.assertRaisesRegex(ValueError,"Extension set changed"):
                module.inspect_ipa(path)
            with zipfile.ZipFile(path,"a") as z:
                z.writestr("Payload/LiveContainer.app/PlugIns/ShareExtension.appex/Info.plist",
                           info(host+".ShareExtension","com.apple.share-services"))
            r=module.inspect_ipa(path)
            self.assertEqual(r["total_bundle_ids"],4)
            self.assertEqual(r["extension_app_ids"],3)

if __name__=="__main__":
    unittest.main()
