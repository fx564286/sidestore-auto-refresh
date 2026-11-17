"""P92 original JIT-less menu + native manual session log + guest/refresh gate split."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
GUEST = (ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
PATCH = ROOT/'integration/apply_scarlet_host.py'
WORKFLOW = (ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P92JITLessMenuAndRecovery(unittest.TestCase):
    def test_real_native_jit_screen_accessible_from_actual_ios17_section(self):
        self.assertIn('NavigationLink {\n                LCJITLessDiagnoseView()', UI)
        self.assertIn('SCARLET_JITLESS_DIAGNOSTIC_ENTRY', UI)
        self.assertIn('jitless_manual_diagnostic_opened', UI)
        self.assertIn('ScarletSigningReadinessPanel()', PATCH.read_text())
        self.assertIn('if #available(iOS 17.0, *)', PATCH.read_text())
        self.assertNotIn('SharedModel.shared', UI)

    def test_guest_signer_gate_no_longer_accidentally_inherits_native_refresh_gate(self):
        self.assertIn('var canAttemptLocalGuestSignerRecovery: Bool', UI)
        local = UI.split('var canAttemptLocalGuestSignerRecovery: Bool {')[1].split('}',1)[0]
        self.assertIn('sideStoreAppGroupAccessible', local)
        self.assertIn('developerTeamEntitled', local)
        self.assertNotIn('signedApplicationIdentifierMatches', local)
        native = UI.split('var canRequestNativeRefresh: Bool {')[1].split('}',1)[0]
        self.assertIn('signedApplicationIdentifierMatches', native)
        self.assertIn('guard readiness.canAttemptLocalGuestSignerRecovery else {', GUEST)
        self.assertIn('"signer_recovery_started"', GUEST)
        self.assertIn('"native_signer_recovery_started"', GUEST)
        self.assertIn('trialExistingSideStoreCertificate(nativeCandidate:', GUEST)
        self.assertIn('restoreOriginal(prefs)', GUEST)
        self.assertIn('LCUtils.validateJITLessSetup { valid, _ in', GUEST)

    def test_original_jit_manual_test_writes_sanitized_exportable_log(self):
        spec=importlib.util.spec_from_file_location('scarlet_p92_integrator', PATCH)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            engine=Path(tmp)
            original=engine/'LiveContainerSwiftUI/Views/Settings/LCJITLessDiagnoseView.swift'
            original.parent.mkdir(parents=True)
            original.write_text('''            }
            .navigationTitle(isLiveProcess ? "LiveProcess Entitlements" : "LiveContainer Entitlements")
            }
            .navigationTitle("lc.settings.jitlessDiagnose".loc)
    func testJITLessMode() {
        isJITLessTestInProgress = true
        LCUtils.validateJITLessSetup { success, error in
            if success {
                successShow = true
            }
        }
    }
''')
            report=module.attach_jitless_diagnostic_scroll_margins(engine)
            updated=original.read_text()
            self.assertTrue(report['manualJITTestRecorded'])
            self.assertIn('jitless_manual_probe_started', updated)
            self.assertIn('jitless_manual_probe_finished', updated)
            self.assertIn('signature_postcheck_invalid', updated)
            self.assertEqual(updated.count('LCUtils.validateJITLessSetup'),1)
            self.assertEqual(updated.count('.scarletDiagnosticScrollMargins()'),2)

    def test_ci_release_has_distinct_p92_identity(self):
        w=WORKFLOW
        self.assertIn('fix/scarlet-v48-r6p92-jitless-diag-guest-recovery-20261117', w)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.92)', w)
        self.assertIn('if "r6p92"', w)
        self.assertIn('Scarlet-Crystal-V48-R6P92-JITLESS-RECOVERY-UNSIGNED.ipa', w)
        self.assertIn('tag=scarlet-v48-r6p92-jitless-recovery-unsigned-20261117', w)

if __name__=='__main__':
    unittest.main()
