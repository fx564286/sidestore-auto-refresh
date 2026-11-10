"""V42 diagnostics only: preserve exact V40 UI and full-screen engine.

No attempt to restore RAM or re-enable unverified LiveProcess resizing.
Source-contract checks, not an actual iPhone process preservation test.
"""
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
G=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
L=(R/'HostApp/ScarletGuestSessionLedger.swift').read_text()
D=(R/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
I=(R/'integration/apply_scarlet_host.py').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class TestV40RollbackAndRuntimeEvidence(unittest.TestCase):
    def test_v41_regression_paths_absent(self):
        for source in (H,G,L,D,I):
            for forbidden in ('ScarletResidentGuestMode.V41',
                              'ScarletResidentGuestSwitchController',
                              'scarletPrepareResident',
                              'scarletActivateResident',
                              'residentControllers',
                              'resident_process_reused'):
                self.assertNotIn(forbidden,source)
        self.assertIn('try await app.runApp(multitask: false)',H)
        self.assertIn('UIDevice.current.userInterfaceIdiom == .phone',H)
        self.assertIn('MultitaskMode.nativeWindow.rawValue',H)
        self.assertNotIn('MultitaskMode.virtualWindow',H)
        self.assertNotIn('try await app.runApp(multitask: true)\n                        ScarletDiagnosticRecorder.shared.record(',H)

    def test_window_and_appearance_are_unchanged(self):
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',G)
        self.assertIn('window.windowLevel == .normal',G)
        self.assertIn('overlay.windowLevel = UIWindow.Level.alert + 1',G)
        self.assertIn('overlay.frame = frame(in: original)',G)
        self.assertIn('UIHostingController(rootView: content)',G)
        self.assertNotIn('windowHostingView.frame = window.bounds',I)
        self.assertNotIn('settings.safeAreaInsetsPortrait = self.view.window.safeAreaInsets',I)
        self.assertIn('legacyScene320x480GeometryRemoved',I)

    def test_only_this_work_session_not_installed_app_list(self):
        self.assertIn('Scarlet.Guest.ActiveSwitcherSession.V40',L)
        self.assertIn('Scarlet.Guest.WorkSessionID.V40',L)
        self.assertIn('cold_host_new_session',L)
        self.assertIn('verified_guest_return_continued',L)
        self.assertIn('memory": "not_verified"',L)
        self.assertIn('switcher_new_work_session',L)
        self.assertIn('switch_cold_handoff',G)
        self.assertIn('"memory": "not_preserved"',G)

    def test_real_runtime_pid_proof_in_guest_not_host_assumption(self):
        self.assertIn('runtime_guest_process_observed',L)
        self.assertIn('processPID: Int32?',L)
        self.assertIn('processPID: ProcessInfo.processInfo.processIdentifier',G)
        self.assertIn('let lastObservedGuestRuntimeID',G.replace('private static var','let'))
        self.assertIn('runtimeGuestID != lastObservedGuestRuntimeID',G)
        self.assertIn('processPID: ProcessInfo.processInfo.processIdentifier',L)
        self.assertIn('fields["process_pid"] = String(pid)',L)
        self.assertIn('"process_pid", "memory"',D)
        self.assertIn('guest_app_group',L)
        self.assertIn('currentProcessStart',L)
        self.assertNotIn('app.appInfo.bundleIdentifier',D)

    def test_refresh_not_claimed_installed(self):
        A=(R/'HostApp/ScarletAutomaticRenewal.swift').read_text()
        self.assertIn('automatic_attempt_deferred',A)
        self.assertIn('retry_interval_not_elapsed',A)
        self.assertIn('installation_verified": "false"',A)
        self.assertIn('installed_profile_unchanged_after_request',A)
        self.assertIn('native_profile_date_advanced_install_unverified',A)

    def test_ci_tag_and_release(self):
        self.assertIn('fix/scarlet-v42-v40-safe-diagnostics-20261110',W)
        self.assertIn('scarlet-v42-unsigned-20261110',W)
        self.assertIn('Scarlet-Crystal-V42-UNSIGNED.ipa',W)

if __name__ == '__main__':
    unittest.main()
