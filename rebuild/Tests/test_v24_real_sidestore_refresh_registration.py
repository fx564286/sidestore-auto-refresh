"""V24: SideStore and SideInstaller refresh paths differ in installed-app DB.

The V23 iPhone log shows SideStore code=1 failures historically, and many
background scheduling events without signed installation receipts. Scarlet
was side-installed with a rewritten Apple bundle ID. A valid LC P12 and an
authenticated SideSign session do not establish registration in SideStore's
separate CoreData and signing Keychain.
"""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
WIRE=(R/"integration/wire_scarlet_auth.py").read_text()
AGENT=(R/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
SUPPORT=(R/"HostApp/ScarletAuthXPCSupport.swift").read_text()
PANEL=(R/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
AUTO=(R/"HostApp/ScarletAutomaticRenewal.swift").read_text()
LEDGER=(R/"HostApp/ScarletGuestSessionLedger.swift").read_text()
GUEST=(R/"HostApp/ScarletFullscreenGuestTab.swift").read_text()

class V24RegistrationGate(unittest.TestCase):
    def test_real_sidestore_managed_app_database_queried_inside_worker(self):
        self.assertIn('DatabaseManager.shared.start()',AGENT)
        self.assertIn('InstalledApp.fetchAppsForRefreshingAll(in: context)',AGENT)
        self.assertIn('Bundle.Info.activeBundleIdentifier',AGENT)
        self.assertIn('$0.resignedBundleIdentifier == realHostID',AGENT)
        self.assertIn('CertificateManager.shared.activeCertificate != nil',AGENT)
        self.assertIn('host_not_managed',AGENT)
        self.assertIn('no_managed_apps',AGENT)
        self.assertIn('sidestore_certificate_missing',AGENT)
        self.assertNotIn('password',AGENT.lower())
        self.assertNotIn('revokeCertificate(',AGENT)
        self.assertNotIn('revokeCertificates(',AGENT)
        # V28 recognises the original SideStore certificateRevoked
        # ERROR but never invokes any Apple certificate revocation API.
        self.assertIn('.certificateRevoked',AGENT)
        self.assertIn('ScarletGuestRefreshAgent.swift.txt',WIRE)
        self.assertIn('isEmbeddedLCRefreshWorker',WIRE)
        self.assertIn('LiveProcess.appex/',WIRE)
        self.assertIn('Bundle.Info.activeBundleURL.pathExtension.lowercased()',WIRE)
        self.assertIn('Bundle.Info.activeBundle.builtInPlugInsURL',WIRE)
        self.assertIn('AltStore/Core/Model/DatabaseManager/DatabaseManager.swift',WIRE)
        self.assertIn('SideStore headless LiveProcess self registration',WIRE)

    def test_native_xpc_protocol_and_callback_not_ui_fake(self):
        self.assertIn('scarletRefreshReadiness:',WIRE)
        self.assertIn('@selector(inspect:)',WIRE)
        self.assertIn('ScarletNativeRefreshInspector',SUPPORT)
        self.assertIn('ScarletNativeAuthTransport.shared.prepare()',SUPPORT)
        self.assertIn('client.scarletRefreshReadiness',SUPPORT)
        self.assertIn('canRefreshHost',SUPPORT)
        self.assertIn('transport_unresponsive',SUPPORT)

    def test_manual_and_automatic_refresh_prove_managed_self_first(self):
        self.assertIn('let nativeState = await ScarletNativeRefreshInspector.inspect()',PANEL)
        self.assertIn('guard nativeState.canRefreshHost else {',PANEL)
        self.assertIn('sidestore_managed_apps_inspected',PANEL)
        self.assertIn('SCARLET_MANAGED_REFRESH_APP_COUNT',PANEL)
        self.assertIn('SCARLET_MANAGED_HOST_REGISTRATION',PANEL)
        self.assertIn('Button(action: requestManualRefresh)',PANEL)
        self.assertIn('SCARLET_NATIVE_REFRESH_NOW',PANEL)
        self.assertIn('Label("지금 갱신"',PANEL)
        self.assertNotIn('Label("SideStore 수동 새로고침"',PANEL)
        self.assertLess(PANEL.index('guard nativeState.canRefreshHost else {'),
                        PANEL.index('ScarletNativeRefreshExecutor.execute()'))
        self.assertIn('automatic_managed_apps_inspected',AUTO)
        self.assertIn('guard nativeState.canRefreshHost else {',AUTO)
        self.assertLess(AUTO.index('guard nativeState.canRefreshHost else {'),
                        AUTO.index('ScarletNativeRefreshExecutor.execute()'))
        self.assertIn('nativeGuidance',AUTO)

    def test_pending_status_and_auth_failure_are_terminally_reconciled(self):
        self.assertIn('orphaned_request_state_reconciled',PANEL)
        self.assertIn('Scarlet.Refresh.LastAttemptStartedAt',PANEL)
        self.assertIn('Scarlet.Refresh.LastAttemptStartedAt',AUTO)
        self.assertIn('차단 · SideStore 로그인 상태 확인 필요',PANEL)
        self.assertIn('ScarletRefreshOutcomeChanged',PANEL)
        self.assertIn('ScarletRefreshOutcomeChanged',AUTO)
        self.assertIn('installation_verified',PANEL)
        self.assertIn('installation_verified',AUTO)

    def test_guest_switch_handoff_is_acknowledged_not_assumed(self):
        self.assertIn('switch_target_boot_ack',LEDGER)
        self.assertIn('switch_target_boot_mismatch',LEDGER)
        self.assertIn('noteSwitchHandoff',LEDGER)
        self.assertIn('confirmSwitchHandoff(runtimeGuestID:',GUEST)
        self.assertIn('ScarletGuestSessionLedger.restore(oldSession)',GUEST)
        self.assertIn('ScarletGuestSessionLedger.cancelSwitchHandoff()',GUEST)
        self.assertIn('let bundleID: String?',GUEST)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',GUEST)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)',GUEST)
        self.assertIn('Scarlet.Guest.ActiveSwitcherSession.V23',LEDGER)

if __name__=="__main__":
    unittest.main()
