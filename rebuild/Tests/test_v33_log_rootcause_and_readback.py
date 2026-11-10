"""V33 regression vs 2026-11-10 V31 diagnostics. These checks
test source contracts only; native compilation and device installs are separate.
"""
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
WORKER=(R/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
HOST=(R/"HostApp/ScarletIntegratedHostView.swift").read_text()
XPC=(R/"HostApp/ScarletAuthXPCSupport.swift").read_text()
AUTO=(R/"HostApp/ScarletAutomaticRenewal.swift").read_text()
MANUAL=(R/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
INTEGRATION=(R/"integration/apply_scarlet_host.py").read_text()
LEDGER=(R/"HostApp/ScarletGuestSessionLedger.swift").read_text()

class V33LogRootCauses(unittest.TestCase):
    def test_original_lc_kernel_signature_readback_before_guest_launch(self):
        self.assertIn('LCMachOUtils.h', INTEGRATION)
        self.assertIn('checkCodeSignature($0)',INTEGRATION)
        self.assertIn('signature_readback_verified',INTEGRATION)
        self.assertIn('signature_readback_failed',INTEGRATION)
        self.assertIn('guard valid else',INTEGRATION)
        self.assertIn('executableURL',INTEGRATION)
        self.assertLess(INTEGRATION.index('checkCodeSignature($0)'),
                        INTEGRATION.index('signing_call_returned'))
        self.assertNotIn('signature_not_read_back',INTEGRATION)

    def test_refresh_record_receipt_is_not_a_claim_of_ios_installation(self):
        self.assertIn('let before = await context.perform', WORKER)
        self.assertIn('let hostResult = results[managedHost.bundleIdentifier]',WORKER)
        self.assertIn('refreshedHost.managedObjectContext',WORKER)
        self.assertIn('after.0 > before.0',WORKER)
        self.assertIn('native_refresh_record_updated_install_unverified',WORKER)
        self.assertIn('native_profile_date_advanced_install_unverified',WORKER)
        self.assertIn('native_operation_returned_unverified',WORKER)
        for reason in ('native_profile_date_advanced_install_unverified',
                        'native_refresh_record_updated_install_unverified'):
            self.assertIn(reason,XPC)
            self.assertIn(reason,MANUAL)
            self.assertIn(reason,AUTO)
        self.assertNotIn('reply(true, "installed")',WORKER)
        self.assertIn('installation_verified": "false"',MANUAL)
        self.assertIn('installation_verified": "false"',AUTO)

    def test_auto_refresh_checks_live_pairing_not_only_saved_login(self):
        self.assertIn('ScarletNativePairingInstaller.inspectPersistedState()',AUTO)
        self.assertIn('automatic_deferred_pairing',AUTO)
        self.assertIn('guard paired else',AUTO)
        self.assertLess(AUTO.index('inspectPersistedState()'),
                        AUTO.index('ScarletNativeRefreshExecutor.execute()'))
        self.assertIn('storedAuthenticated()', AUTO)
        self.assertLess(AUTO.index('guard nativeState.canRefreshHost else'),
                        AUTO.index('prefs.set(Date(), forKey: attemptKey)'))
        self.assertIn('ScarletSigningReadiness.inspect()',AUTO)

    def test_switcher_same_boot_history_without_fake_ram_scene(self):
        self.assertIn('Scarlet.Guest.LaunchBootEpoch.V40',LEDGER)
        self.assertIn('Scarlet.Guest.DepartedTicket.V40',LEDGER)
        self.assertIn('ProcessInfo.processInfo.systemUptime',LEDGER)
        self.assertIn('verified_guest_departure_continued',LEDGER)
        self.assertIn('verified_guest_return_continued',LEDGER)
        self.assertIn('cold_host_new_session',LEDGER)
        self.assertIn('store.set(empty, forKey: key)',LEDGER)
        self.assertNotIn('sameBoot && !recent().isEmpty',LEDGER)
        self.assertIn('departureIsValid(departure, workID: workID, at: now)',LEDGER)
        self.assertIn('memory": "not_preserved"',
                      (R/"HostApp/ScarletFullscreenGuestTab.swift").read_text())
        self.assertIn('try await app.runApp()',HOST)

    def test_no_credentials_or_app_ids_modified(self):
        for source in (WORKER,AUTO,LEDGER):
            self.assertNotIn('removePersistentDomain(',source)
            self.assertNotIn('revokeCertificate(',source)
        self.assertIn('com.kdt.livecontainer.P8EZT3U5N4',AUTO)
        self.assertIn('pairing_saved_and_transport_ready',WORKER)

if __name__=="__main__": unittest.main()
