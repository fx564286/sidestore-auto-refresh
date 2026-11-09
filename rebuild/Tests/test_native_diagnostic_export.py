"""Scarlet Crystal in-app diagnostics and fullscreen native LC settings.

Static contract and upstream-injection fixture are NOT physical iPhone tests.
"""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
LOGIN=(ROOT/"HostApp/ScarletAppleIDLoginSheet.swift").read_text()
LOG=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()

def integrator():
    spec=importlib.util.spec_from_file_location("diagnostic_integrator",ROOT/"integration/apply_scarlet_host.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class FullSizeSettingsAndOnDeviceLog(unittest.TestCase):
    def test_original_native_settings_owns_full_screen_and_single_title(self):
        segment=UI[UI.index("            if tab == .settings {"):
                   UI.index("            } else if tab == .tweaks {")]
        self.assertIn("nativeSettings()",segment)
        self.assertIn(".frame(maxWidth: .infinity, maxHeight: .infinity)",segment)
        self.assertIn("SCARLET_INLINE_NATIVE_LC_SETTINGS",segment)
        self.assertNotIn('Text("설정")',segment)
        self.assertNotIn("VStack(",segment)
        self.assertNotIn(".padding(",segment)
        self.assertIn("LCSettingsView()",HOST)

    def test_original_lc_settings_is_extended_not_recreated(self):
        fixture='''import SwiftUI
struct LCSettingsView: View {
    var body: some View {
        NavigationView {
            Form {
                Text("original setting")
''' + "".join(
            '                Section {\n'
            f'                    Text("Original setting {index}")\n'
            '                } header: {\n'
            '                    Text("Original section")\n'
            '                } footer: {\n'
            '                    Text("Unmodified control")\n'
            '                }\n'
            for index in range(15)
        ) + '''            }
            .navigationBarTitle("lc.tabView.settings".loc)
        }
        .navigationViewStyle(StackNavigationViewStyle())
    }
}
'''

        with tempfile.TemporaryDirectory() as tmp:
            engine=Path(tmp)
            file=engine/"LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift"
            file.parent.mkdir(parents=True)
            file.write_text(fixture)
            report=integrator().attach_native_settings_diagnostics(engine)
            source=file.read_text()
            self.assertTrue(report["singleTitle"])
            self.assertEqual(report["styledSections"],16)
            self.assertTrue(report["diagnosticSectionAtTop"])
            self.assertIn('Text("original setting")',source)
            self.assertIn("SCARLET_NATIVE_DIAGNOSTICS_ENTRY",source)
            self.assertIn(".scarletNativeListTheme()",source)
            self.assertIn(".scarletSettingsScrollLimit()",source)
            self.assertIn(".scarletNativeListTheme()\\n            .scarletSettingsScrollLimit()",source.replace("\n", "\\n"))
            self.assertNotIn(".scarletDockScrollClearance()",source)
            self.assertEqual(source.count(".listRowBackground("),16)
            self.assertIn("ScarletDiagnosticLogView()",source)
            self.assertIn("ScarletAppleIDLoginSheet(",source)
            self.assertEqual(source.count("NavigationView {"),1)
            self.assertEqual(source.count("Form {"),1)

    def test_logger_jsonl_bounded_and_rotated_without_guest_deletion(self):
        for required in ("session.jsonl","maxFileBytes = 1_500_000",
                         "retainedFiles = 4", "JSONSerialization.data",
                         "ISO8601DateFormatter", "FileHandle(forWritingTo:",
                         "readRecent(maxLines:", "makeShareFile()",
                         "SCARLET_DIAGNOSTICS_VIEW", "ShareLink(item:",
                         "SCARLET_DIAGNOSTICS_SHARE"):
            self.assertIn(required,LOG)
        self.assertNotIn("URLSession",LOG)
        self.assertNotIn("keychain",LOG.lower())
        self.assertNotIn("AppGroup",LOG)
        self.assertIn("allowedFields.contains(key)",LOG)
        self.assertIn('return "[REDACTED]"',LOG)
        self.assertIn("guestReference(_ identifier:",LOG)

    def test_traces_action_guest_and_layout_without_logging_secret_values(self):
        for required in ("recordTab(", "recordLayout()", "safe_top_pt",
                         "safe_bottom_pt", "orientation_observed",
                         "launch_requested", "launch_failed", "install_blocked",
                         "transport_unverified", "source_actions_visible",
                         "memory_warning", "scene_phase"):
            self.assertIn(required,HOST)
        for required in ("twofactor_prompt_requested", "twofactor_code_submitted",
                         "transport_unverified", "request_failed", "login_ui_closed"):
            self.assertIn(required,LOGIN)
        self.assertNotIn("fields: [\"password\"",LOGIN)
        self.assertNotIn("fields: [\"appleID\"",LOGIN)
        self.assertNotIn("fields: [\"verificationCode\"",LOGIN)

    def test_native_guest_manager_and_original_settings_emit_import_events(self):
        for required in ("file_import_requested","import_pipeline_completed",
                         "import_pipeline_failed", "url_import_requested",
                         "nativeSettingsDiagnostics", "ScarletDiagnosticRecorder.swift",
                         "dynamic_colors_changed", "dark_icon_changed",
                         "jit_provider_changed"):
            self.assertIn(required,PATCH)
        self.assertNotIn("shutil.rmtree(",PATCH)
        self.assertNotIn("nukeSideStore()",PATCH)

    def test_warnings_about_limitations_are_in_view(self):
        self.assertIn("iOS fatal crash .ips",LOG)
        self.assertIn("auth",LOGIN)
        self.assertIn("reason",HOST)
        self.assertNotIn("http://",LOG)
        self.assertNotIn("https://",LOG)

if __name__=="__main__":
    unittest.main()
