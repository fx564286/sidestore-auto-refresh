"""Scarlet Crystal original V3 account + JIT Settings parity gate."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "v181settings", ROOT/"scripts/patch_v181_v3_settings_port.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SHELL="import SwiftUI\nstruct V3AccountSettings: View { var body: some View { EmptyView() } }\n"
FORM="""struct LCSettingsView: View {
    var body: some View {
        NavigationView {
            Form {
                // Retain legacy Return settings until V107 removes them
                NavigationLink(destination: LCJITLessDiagnoseView()) { EmptyView() }
            }
        }
    }
}
"""

class SettingsPortTests(unittest.TestCase):
    def test_install_account_and_preserve_jit_original(self):
        out=mod.patch(FORM,SHELL)
        self.assertEqual(out,mod.patch(out,SHELL))
        self.assertEqual(out.count("V3AccountSettings()"),1)
        self.assertIn("LCJITLessDiagnoseView()",out)
        self.assertIn("legacy Return settings",out)

    def test_missing_real_ui_blocks_implementation(self):
        with self.assertRaisesRegex(ValueError,"implementation is missing"):
            mod.patch(FORM,"import SwiftUI")
        with self.assertRaisesRegex(ValueError,"JIT-Less"):
            mod.patch(FORM.replace("LCJITLessDiagnoseView()","OldView()"),SHELL)

    def test_original_settings_form_drift_fails(self):
        with self.assertRaisesRegex(ValueError,"drifted"):
            mod.patch(FORM.replace("            Form {","            VStack {"),SHELL)

if __name__=="__main__":
    unittest.main()
