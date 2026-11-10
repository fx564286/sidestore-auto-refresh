"""V40: fresh Scarlet work, then only A and B launched in THIS work.

Source-contract tests for the actual V40 code plus deterministic reference
transitions. Not an iPhone process-RAM or last-screen restoration test.
"""
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
L=(R/'HostApp/ScarletGuestSessionLedger.swift').read_text()
G=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class V40TrueActiveWork(unittest.TestCase):
    def test_no_migration_from_old_v37_kakao_instagram(self):
        self.assertIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V43"',L)
        self.assertIn('Scarlet.Guest.WorkSessionID.V43',L)
        self.assertIn('Scarlet.Guest.HostReturnTicket.V43',L)
        self.assertIn('Scarlet.Guest.DepartedTicket.V43',L)
        self.assertNotIn('store.data(forKey: "Scarlet.Guest.ActiveSwitcherSession.V37")',L)
        self.assertNotIn('store.data(forKey: "Scarlet.Guest.HostReturnTicket.V37")',L)
        self.assertIn('static func startFreshWorkSession()',L)
        self.assertIn('store.set(id, forKey: sessionIDKey)',L)
        self.assertIn('JSONEncoder().encode([Entry]())',L)
        self.assertIn('switcher_new_work_session',L)
        self.assertIn('switcher_work_session_started',L)
        self.assertIn('cold_host_new_session',L)
        self.assertIn('String(recent().count)',L)

    def test_old_date_only_ticket_can_never_implicitly_resume_old_work(self):
        self.assertIn('private struct HostReturn: Codable',L)
        self.assertIn('let workID: String',L)
        self.assertIn('let folder: String',L)
        self.assertIn('departure.workID == workID',L)
        self.assertIn('ticket.workID == workID',L)
        self.assertIn('ticket.folder == departure?.folder',L)
        self.assertIn('abs(departure.bootEpoch - bootEpoch()) < 120',L)
        self.assertIn('age >= 0 && age <= guestDepartureValidity',L)
        self.assertIn('recent().contains(where: { $0.folder == departure.folder })',L)
        self.assertIn('store.removeObject(forKey: guestDepartedKey)',L)
        self.assertIn('store.removeObject(forKey: hostReturnKey)',L)
        self.assertIn('let legitimateGuest = departureIsValid(',L)
        self.assertNotIn('explicitReturn ||',L)
        self.assertNotIn('sameBoot && !recent().isEmpty',L)

    def test_guest_return_tied_to_actual_runtime_guest(self):
        self.assertIn('static func beginReturnToHost(folder: String)',L)
        self.assertIn('noteGuestDeparted(folder: folder)',L)
        self.assertIn('guard let activeGuestFolder else',G)
        self.assertIn('ScarletGuestSessionLedger.beginReturnToHost(\n                    folder: activeGuestFolder)',G)
        self.assertIn('UIApplication.willResignActiveNotification',G)
        self.assertIn('ScarletGuestSessionLedger.noteGuestDeparted(folder: id)',G)
        self.assertIn('private static var activeGuestFolder: String?',G)
        self.assertIn('activeGuestFolder != currentGuest.id',G)
        self.assertIn('ScarletGuestSessionLedger.prepareForHostAppearance()',H)
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(',H)

    def test_selected_key_never_overrides_runtime_identity(self):
        self.assertIn('let isCurrent = hasRuntimeIdentity && matchesRuntime',G)
        self.assertNotIn(': (folder == selected || bundleID == selected)',G)
        self.assertIn('let runtimeID = guestIdentifier?.trimmingCharacters',G)
        self.assertIn('let originalBundleID = meta["LCOrignalBundleIdentifier"] as? String',G)
        self.assertIn('let recentFolders = Set(recent.map(\\.folder))',G)
        self.assertIn('guard isCurrent || activeScene || recentFolders.contains(folder) else',G)
        self.assertIn('UIDevice.current.userInterfaceIdiom == .pad',G)
        self.assertIn('switcher_launch_rejected_without_work',L)

    def test_a_b_only_in_one_fresh_session_reference(self):
        # Reference state machine, not a substitute for device integration QA.
        persisted_v37=["Kakao.app","Instagram.app"]
        work=[]                              # fresh V40 host: 0
        self.assertEqual(work,[])
        work=["A.app"]+ [x for x in work if x!="A.app"]
        self.assertEqual(work,["A.app"])    # after first actual launch
        work=["B.app"]+ [x for x in work if x!="B.app"]
        self.assertEqual(set(work),{"A.app","B.app"})
        self.assertEqual(len(work),2)
        # switching A only promotes existing A within CURRENT work
        work=["A.app"]+[x for x in work if x!="A.app"]
        self.assertEqual(work,["A.app","B.app"])
        self.assertFalse(set(work) & set(persisted_v37))
        work=[]  # unrelated new host launch without verified guest handoff
        self.assertEqual(work,[])

    def test_reuse_original_fullscreen_does_not_claim_ram_resumption(self):
        self.assertIn('try await app.runApp(multitask: false)',H)
        self.assertIn('switch_cold_handoff',G)
        self.assertIn('"memory": "not_preserved"',G)
        self.assertNotIn('MultitaskMode.virtualWindow',H)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',G)

    def test_new_release_workflow(self):
        self.assertIn('fix/scarlet-v40-clean-work-session-20261110',W)
        self.assertIn('scarlet-v40-unsigned-20261110',W)
        self.assertIn('Scarlet-Crystal-V40-UNSIGNED.ipa',W)

if __name__=='__main__':
    unittest.main()
