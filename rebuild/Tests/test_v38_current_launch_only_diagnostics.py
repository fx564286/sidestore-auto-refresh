"""Regression: V38 default report contains only this process launch.

These checks are source-contract checks; real iPhone reporting is verified
by a V38 on-device export. Guest data and user credentials are untouched.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
AUTOMATIC=(ROOT/'HostApp/ScarletAutomaticRenewal.swift').read_text()

class CurrentLaunchOnly(unittest.TestCase):
    def test_rotation_occurs_on_recorder_process_init_not_midrun(self):
        start=S.index('private init()')
        end=S.index('private func logURL',start)
        init=S[start:end]
        self.assertIn('if fm.fileExists(atPath: current.path)',init)
        self.assertIn('try? fm.moveItem(at: previous, to: next)',init)
        self.assertIn('fm.createFile(atPath: current.path, contents: nil)',init)
        record=S[S.index('func record('):S.index('func recordError(')]
        self.assertNotIn('fm.moveItem(',record)
        self.assertIn('Data(previous.suffix(maxFileBytes / 2))',record)
        self.assertIn('maxFileBytes = 1_500_000',S)
        self.assertIn('retainedFiles = 4',S)

    def test_share_and_view_default_current_process_only(self):
        self.assertIn('func makeShareFile(includeHistory: Bool = false)',S)
        self.assertIn('func readRecent(maxLines: Int = 350)',S)
        self.assertIn('readRecent(maxLines: maxLines, includeHistory: false)',S)
        self.assertIn('? Array((0..<retainedFiles).reversed()) : [0]',S)
        self.assertIn('LogScope:',S)
        self.assertIn('CurrentSession:',S)
        self.assertIn('CurrentLaunchAt:',S)
        self.assertIn('Scarlet-Crystal-',S)
        self.assertIn('CurrentRun',S)
        self.assertIn('History',S)
        self.assertIn('Text("이번 실행").tag(false)',S)
        self.assertIn('Text("이전 기록 포함").tag(true)',S)
        self.assertIn('SCARLET_DIAGNOSTICS_LOG_SCOPE',S)
        self.assertIn('makeShareFile(\n            includeHistory: includeHistory)',S)

    def test_cannot_accidentally_erase_other_app_data(self):
        self.assertNotIn('removePersistentDomain(',S)
        self.assertNotIn('SecItemDelete',S)
        self.assertNotIn('UserDefaults.standard.remove',S)
        self.assertNotIn('FileManager.default.removeItem(atPath: NSHomeDirectory()',S)
        self.assertIn('directory = root.appendingPathComponent(',S)
        self.assertIn('ScarletCrystal/Diagnostics',S)
        self.assertIn('allowedFields.contains(key)',S)
        self.assertIn('return "[REDACTED]"',S)

    def test_cross_process_guest_trace_never_replays_old_events(self):
        trace=(ROOT/'HostApp/ScarletGuestSessionLedger.swift').read_text()
        injector=(ROOT/'integration/apply_scarlet_host.py').read_text()
        self.assertIn('let createdAt: Date?',trace)
        self.assertIn('createdAt: Date()',trace)
        self.assertIn('ScarletDiagnosticRecorder.shared.currentProcessStartDate',trace)
        self.assertIn('entry.createdAt.map { $0 >= currentProcessStart } ?? false',trace)
        self.assertIn('timeIntervalSinceReferenceDate',injector)
        self.assertIn('@"createdAt"',injector)

    def test_auto_background_receipt_does_not_claim_installation(self):
        self.assertIn('automatic_background_task_completed',AUTOMATIC)
        self.assertIn('automatic_attempt_deferred',AUTOMATIC)
        self.assertIn('skipped_not_due',AUTOMATIC)
        self.assertIn('lastCheckWasDeferred = true',AUTOMATIC)
        self.assertIn('installation_verified": "false"',AUTOMATIC)
        self.assertIn('installation_verified": "false"',AUTOMATIC)
        self.assertIn('static func verifyNewProcess()',AUTOMATIC)
        self.assertIn('installed_profile_changed_after_request',AUTOMATIC)

    def test_iphone_original_screen_geometry_protected(self):
        host=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
        integrator=(ROOT/'integration/apply_scarlet_host.py').read_text()
        self.assertIn('try await app.runApp(multitask: false)',host)
        self.assertNotIn('MultitaskMode.virtualWindow',host)
        self.assertNotIn('ScarletGuestLiveBridge',host)
        self.assertIn('legacyVisualSourceRemoved',integrator)
        self.assertIn('legacyScene320x480GeometryRemoved',integrator)
        self.assertIn('original_fullscreen_policy',host)

if __name__=='__main__':unittest.main()
