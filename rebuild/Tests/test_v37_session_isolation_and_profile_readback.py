"""V37 iPhone regression for stale Kakao/Instagram sessions + truthful renewal.

All tests use the actual generated production source contracts. iOS runtime,
signing and final app installation must still be checked separately.
"""
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
L=(R/'HostApp/ScarletGuestSessionLedger.swift').read_text()
G=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
A=(R/'HostApp/ScarletAutomaticRenewal.swift').read_text()
M=(R/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class V37SessionAndRefresh(unittest.TestCase):
    def test_never_migrate_old_kakao_insta_session_into_current_work(self):
        self.assertIn('Scarlet.Guest.ActiveSwitcherSession.V40', L)
        self.assertIn('Scarlet.Guest.DepartedTicket.V40', L)
        self.assertIn('Scarlet.Guest.HostReturnTicket.V40',L)
        self.assertIn('Legacy key: Scarlet.Guest.RecentSessions.V14',L)
        self.assertIn('Legacy key: Scarlet.Guest.ActiveSwitcherSession.V19',L)
        self.assertNotIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V23"',L)
        self.assertNotIn('sameBoot && !recent().isEmpty',L)
        self.assertIn('departureIsValid(departure, workID: workID, at: now)',L)
        self.assertIn('store.set(empty, forKey: key)',L)
        self.assertIn('cold_host_new_session',L)
        self.assertIn('static func reconcileHostForeground()',L)
        self.assertIn('static func beginNewWork()',L)
        self.assertIn('switcher_new_work_session',L)
        self.assertIn('ScarletGuestSessionLedger.reconcileHostForeground()',H)

    def test_a_home_b_continuation_requires_observed_guest_recent_handoff(self):
        self.assertIn('private static let guestDepartureValidity: TimeInterval = 120',L)
        self.assertIn('age >= 0 && age <= guestDepartureValidity',L)
        self.assertIn('recent().contains(where: { $0.folder == departure.folder })',L)
        self.assertIn('abs(departure.bootEpoch - bootEpoch()) < 120',L)
        self.assertIn('store.removeObject(forKey: guestDepartedKey)',L)
        self.assertIn('verified_guest_departure_continued',L)
        self.assertIn('static func noteGuestDeparted(folder: String)',L)
        self.assertIn('UIApplication.willResignActiveNotification',G)
        self.assertIn('ScarletGuestSessionLedger.noteGuestDeparted(folder: id)',G)
        self.assertIn('activeGuestFolder != currentGuest.id',G)
        self.assertIn('let currentGuest = installedApps(guestIdentifier: runtimeGuestID)',G)
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(',G)

    def test_no_stale_native_scene_can_show_as_live_on_iphone(self):
        self.assertIn('let activeScene = UIDevice.current.userInterfaceIdiom == .pad',G)
        self.assertIn('guard isCurrent || activeScene || recentFolders.contains(folder)',G)
        self.assertIn('private static let maxItems = 8',L)
        self.assertIn('runApp(multitask: false)',H)
        self.assertNotIn('MultitaskMode.virtualWindow',H)
        self.assertNotIn('ScarletGuestLiveBridge',G)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',G)

    def test_real_installed_profile_readback_is_separate_from_database(self):
        self.assertIn('import CryptoKit',A)
        self.assertIn('Bundle.main.bundleURL.appendingPathComponent(',A)
        self.assertIn('"embedded.mobileprovision"',A)
        self.assertIn('SHA256.hash(data: data)',A)
        self.assertIn('static func beginRequest(source: String)',A)
        self.assertIn('static func verifyNewProcess()',A)
        self.assertIn('owner != processMarker',A)
        self.assertIn('if after != before {',A)
        self.assertIn('"installed_profile_changed_after_request"',A)
        self.assertIn('"installed_profile_unchanged_after_request"',A)
        self.assertIn('"installation_verified": "false"',A)
        self.assertNotIn('"installation_verified": "true"',A)
        self.assertIn('ScarletInstalledProfileReadback.verifyNewProcess()',H)
        self.assertIn('ScarletInstalledProfileReadback.beginRequest(source: "manual")',M)
        self.assertIn('ScarletInstalledProfileReadback.beginRequest(source: "automatic")',A)
        self.assertIn('ScarletInstalledProfileReadback.discardFailedRequest()',A)
        self.assertIn('ScarletInstalledProfileReadback.discardFailedRequest()',M)

    def test_preserves_guest_data_original_display_and_identity(self):
        self.assertIn('com.kdt.livecontainer.P8EZT3U5N4',A)
        self.assertNotIn('removePersistentDomain(',L)
        self.assertNotIn('deleteApp(',L)
        self.assertIn('fix/scarlet-v37-session-refresh-20261110',W)
        self.assertIn('Scarlet-Crystal-V37-UNSIGNED.ipa',W)

if __name__ == '__main__':
    unittest.main()
