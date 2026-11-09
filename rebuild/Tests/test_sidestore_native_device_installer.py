"""Headless on-device installer integration source contracts.

No SideInstaller third-party code or release binary is imported. Only the
pinned SideStore AppManager and same-team App Group are used. These tests
check the XPC contract; physical signing, pairing and install need an iPhone.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WIRE=(ROOT/"integration/wire_scarlet_auth.py").read_text()
WORKER=(ROOT/"integration/ScarletDeviceInstallAgent.swift.txt").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
GLASS=(ROOT/"HostApp/ScarletNativeGlass.swift").read_text()

class NativeDeviceInstallerContract(unittest.TestCase):
    def test_no_sideinstaller_binary_or_ui_dependency(self):
        self.assertIn("headless_appmanager",HOST)
        self.assertIn('AppManager.shared.install(.url(fileURL))',WORKER)
        self.assertNotIn('sideinstaller://',HOST)
        self.assertNotIn('SideInstallerApp',WIRE)
        self.assertNotIn('SideInstallerApp',WORKER)
        self.assertNotIn('LCUtils.openSideStore(',HOST)
        self.assertIn('prepareDeviceIPAInstall(selected)',HOST)

    def test_same_group_and_staging_contract(self):
        group='group.com.SideStore.SideStore.P8EZT3U5N4'
        self.assertIn(group,HOST)
        self.assertIn(group,WORKER)
        self.assertIn(group,WIRE)
        self.assertIn('ScarletDeviceInstall',WORKER)
        self.assertIn('ScarletDeviceInstall',HOST)
        self.assertIn('stagedIPA.standardizedFileURL.resolvingSymlinksInPath()',WIRE)
        self.assertIn('fileURL.deletingLastPathComponent() == workDirectory',WORKER)
        self.assertIn('!filename.contains("..")',WORKER)

    def test_hardened_existing_certificate_policy(self):
        self.assertIn('CertificateManager.shared.loadActiveCertificate()',WORKER)
        self.assertIn('notify("certificate_missing")',WORKER)
        self.assertNotIn('revokeCertificate(',WORKER)
        self.assertNotIn('requestCertificate(',WORKER)
        self.assertIn('ScarletSigningReadiness.inspect()',HOST)
        self.assertIn('readiness.canRequestNativeRefresh',HOST)
        self.assertIn('storedAuthenticated()',HOST)

    def test_worker_xpc_finish_is_an_actual_appmanager_result(self):
        self.assertIn('identifier: "scarlet.install.ipa"',WIRE)
        self.assertIn('name:@"ScarletDeviceInstallCompleted"',WIRE)
        self.assertIn('handler.server finish:nil',WIRE)
        self.assertIn('handler.server finish:[@"scarlet.install."',WIRE)
        self.assertIn('withCheckedThrowingContinuation',WORKER)
        self.assertIn('continuation.resume(with: result)',WORKER)
        self.assertIn('notify("installed")',WORKER)

    def test_original_files_not_deleted_and_no_fake_success(self):
        self.assertIn('source.startAccessingSecurityScopedResource()',HOST)
        self.assertIn('FileManager.default.copyItem(at: source, to: staged)',HOST)
        self.assertIn('defer { try? FileManager.default.removeItem(at: staged) }',HOST)
        self.assertIn('install_operation_returned',HOST)
        self.assertIn('install_failed',HOST)
        self.assertIn('native_install_failed',HOST)
        self.assertNotIn('transport_unverified',HOST)

    def test_device_progress_sheet_swipe_reopen_without_duplicate_card(self):
        sheet=HOST.split('.sheet(isPresented: $showDeviceInstallSheet)',1)[1].split(
            '.sheet(isPresented: $showSourceDownloadSheet',1)[0]
        self.assertIn('SCARLET_NATIVE_DEVICE_INSTALL_SHEET',sheet)
        self.assertIn('.presentationDragIndicator(.visible)',sheet)
        self.assertIn('if deviceInstallRunning',sheet)
        self.assertNotIn('Button("내리기")',sheet)
        self.assertIn('SCARLET_REOPEN_MINIMIZED_INSTALL',UI)
        self.assertIn('onShowActiveInstall: openActiveInstallProgress',HOST)

    def test_refresh_and_original_settings_scroll_regression_preserved(self):
        self.assertIn('RefreshAllAppsIntent().perform()', (
            ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text())
        self.assertIn('func scarletSettingsScrollLimit()',GLASS)
        self.assertIn('scarletSettingsScrollLimit()', (
            ROOT/"integration/apply_scarlet_host.py").read_text())
        self.assertIn('.tabBarMinimizeBehavior(.onScrollDown)',UI)

if __name__=="__main__":
    unittest.main()
