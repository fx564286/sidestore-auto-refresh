"""P110: JIT-less pushed Form's native navigation top edge and wide identity rows.
Only static/source integration tests; no signed iPhone screenshot claim.
"""
from pathlib import Path
import unittest, importlib.util, shutil, tempfile
R=Path(__file__).resolve().parents[2]
GLASS=(R/'rebuild/HostApp/ScarletNativeGlass.swift').read_text()
PATCH=R/'rebuild/integration/apply_scarlet_host.py'
FLOW=(R/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class OriginalLCJITLessNavigation(unittest.TestCase):
    def test_native_top_scroll_effect_restored_only_inside_diagnostic_helper(self):
        section=GLASS.split('func scarletDiagnosticScrollMargins() -> some View {',1)[1].split('// The actual iOS',1)[0]
        self.assertIn('.scrollEdgeEffectHidden(true, for: .bottom)',section)
        self.assertNotIn('.scrollEdgeEffectHidden(true, for: .all)',section)
        self.assertIn('self.contentMargins(.bottom, 84, for: .scrollContent)',section)
    def test_pinned_original_lc_full_width_rows_and_native_test_unchanged(self):
        spec=importlib.util.spec_from_file_location('p110_integrator',PATCH)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        # CI runners do not have our local /workspace reference checkout.
        # Use the SAME exact deterministic pinned-structure fixture on Linux
        # and macOS. The full upstream pin is verified in the build integrator.
        s="""struct LCEntitlementView: View {
    var body: some View {
            Form {
                Text("Entitlements")
            }
            .navigationTitle(isLiveProcess ? "LiveProcess Entitlements" : "LiveContainer Entitlements")
    }
}
struct LCJITLessDiagnoseView : View {
    let storeName = LCUtils.getStoreName()
    var body: some View {
        if loaded {
            Form {
                Section {
                    HStack {
                        Text("lc.jitlessDiag.bundleId".loc)
                        Spacer()
                        Text(Bundle.main.bundleIdentifier ?? "lc.common.unknown".loc)
                            .foregroundStyle(.gray)
                            .textSelection(.enabled)
                    }
                    HStack {
                        Text("lc.jitlessDiag.appGroupId".loc)
                        Spacer()
                        Text(appGroupId)
                            .foregroundStyle(appGroupId == "Unknown" ? .red : .green)
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
            target=Path(tmp)/'LiveContainerSwiftUI/Views/Settings/LCJITLessDiagnoseView.swift'
            target.parent.mkdir(parents=True);target.write_text(s)
            mod.attach_jitless_diagnostic_scroll_margins(Path(tmp))
            built=target.read_text()
        self.assertEqual(built.count('VStack(alignment: .leading, spacing: 5)'),2)
        self.assertEqual(built.count('SCARLET_JITLESS_HOST_BUNDLE_FULLWIDTH'),1)
        self.assertEqual(built.count('SCARLET_JITLESS_HOST_GROUP_FULLWIDTH'),1)
        self.assertIn('LCUtils.validateJITLessSetup { success, error in',built)
        self.assertIn('ScarletJITLessSelectedAccountPanel()',built)
    def test_p110_release_identity_and_binary_gate(self):
        for marker in ('fix/scarlet-v48-r6p110-jitless-native-navigation-20261118',
                       '--host-build-version 3.8.110',
                       'scarlet-v48-r6p110-jitless-navigation-unsigned-20261118',
                       'Scarlet-Crystal-V48-R6P110-JITLESS-NAV-UNSIGNED.ipa'):
            self.assertIn(marker,FLOW)
        for marker in ('b"SCARLET_JITLESS_HOST_BUNDLE_FULLWIDTH"',
                       'b"SCARLET_JITLESS_HOST_GROUP_FULLWIDTH"'):
            self.assertIn(marker,FLOW)
        gate=FLOW.split('publish-unsigned-github-release:',1)[1].split('runs-on: ubuntu-24.04',1)[0]
        self.assertIn("github.ref == 'refs/heads/fix/scarlet-v48-r6p110-jitless-native-navigation-20261118'",gate)

if __name__=='__main__':unittest.main()
