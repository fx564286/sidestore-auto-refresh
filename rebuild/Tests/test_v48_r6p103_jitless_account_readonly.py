"""P103 JIT-less selected-account read-only context without signer route changes."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
HOST=(ROOT/"rebuild/HostApp/ScarletSigningReadinessPanel.swift").read_text()
PATCH=ROOT/"rebuild/integration/apply_scarlet_host.py"
GUEST=(ROOT/"rebuild/HostApp/ScarletIntegratedHostView.swift").read_text()

class JITLessAccountIsolation(unittest.TestCase):
    def test_account_specific_readonly_rows(self):
        view=HOST.split("struct ScarletJITLessSelectedAccountPanel:",1)[1].split("struct ScarletSigningReadiness",1)[0]
        for item in ("ScarletNativeSavedAccounts.list()", "ForEach(accounts)",
                     "account.id", "account.teamID", "account.certificateReady",
                     "account.ownerVerified", "account.managedAppCount",
                     "account.active", "account.teamID != host"):
            self.assertIn(item,view)
        self.assertIn("설치된 호스트 서명팀",view)
        self.assertIn("Apple ID 전환으로 바뀌지 않습니다.",view)
        for forbidden in ("activate(", "issueInstallCertificate(",
                          "setActiveCertificate(", "SecItemDelete(",
                          "revokeCertificate(", "signApp(", "LCUtils.validateJITLessSetup"):
            self.assertNotIn(forbidden,view.split(".task {",1)[1])
        self.assertNotIn("ScarletDiagnosticRecorder.shared.record",view)

    def test_integrated_original_jitless_form_keeps_original_test_and_host(self):
        spec=importlib.util.spec_from_file_location("scarlet_p103_integrator",PATCH)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        source="""struct LCEntitlementView: View {
    var body: some View {
            Form {
                Text("Entitlements")
            }
            .navigationTitle(isLiveProcess ? "LiveProcess Entitlements" : "LiveContainer Entitlements")
    }
}
struct LCJITLessDiagnoseView : View {
    var body: some View {
        if loaded {
            Form {
                Section {
                    HStack {
                        Text("lc.jitlessDiag.bundleId".loc)
                        Text(Bundle.main.bundleIdentifier ?? "lc.common.unknown".loc)
                    }
                }
            }
            .navigationTitle("lc.settings.jitlessDiagnose".loc)
        }
    }
    func testJITLessMode() {
        isJITLessTestInProgress = true
        LCUtils.validateJITLessSetup { success, error in
            if success { successShow = true }
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"LiveContainerSwiftUI/Views/Settings/LCJITLessDiagnoseView.swift"
            target.parent.mkdir(parents=True)
            target.write_text(source)
            mod.attach_jitless_diagnostic_scroll_margins(Path(tmp))
            result=target.read_text()
        self.assertEqual(result.count("ScarletJITLessSelectedAccountPanel()"),1)
        self.assertEqual(result.count("LCUtils.validateJITLessSetup"),1)
        self.assertEqual(result.count(".scarletDiagnosticScrollMargins()"),2)
        self.assertIn('Text(Bundle.main.bundleIdentifier ?? "lc.common.unknown".loc)',result)

    def test_unique_p103_build_identity_and_preserved_p102(self):
        w=(ROOT/".github/workflows/scarlet-paired-engines-build.yml").read_text()
        self.assertIn("fix/scarlet-v48-r6p103-jitless-account-view-20261118",w)
        self.assertIn("SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.103)",w)
        self.assertIn('if "r6p103"',w)
        self.assertIn("SCARLET_JITLESS_SELECTED_ACCOUNT",w)
        self.assertIn("Scarlet-Crystal-V48-R6P103-JITLESS-ACCOUNT-UNSIGNED.ipa",w)
        self.assertIn("SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.102)",w)

    def test_original_guest_signer_and_navigation_untouched(self):
        self.assertIn('NavigationLink {\n                LCJITLessDiagnoseView()',HOST)
        self.assertIn("LCUtils.validateJITLessSetup { valid, _ in",GUEST)
        self.assertIn("trialExistingSideStoreCertificate(nativeCandidate:",GUEST)
        self.assertIn("restoreOriginal(prefs)",GUEST)

if __name__ == "__main__": unittest.main()
