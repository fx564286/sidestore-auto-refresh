"""Regression: settings tap path must work without SideStore; mutation must fail closed."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/patch_v191_settings_control_actions.py"
spec=importlib.util.spec_from_file_location("settings_control_actions",p)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

BRIDGELESS_HOST_LOG = '''
// SCARLET_V183_HOST_LOG_FALLBACK
enum ScarletV183Event: String {
    case logsOpened = "logs.opened"
}
enum ScarletV183HostLog {
    static func record(_ event: ScarletV183Event) {}
}
'''

SOURCE=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text()
SHELL=BRIDGELESS_HOST_LOG+SOURCE
LOCAL_SETTINGS='''struct LCSettingsView: View {
    func clearNotifications() {
        UNUserNotificationCenter.current().removeAllPendingNotificationRequests()
    }
}
'''


class SettingsActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=mod.patch_shell(SHELL)

    def test_host_local_button_has_independent_visual_and_log_receipt(self):
        view=self.out.split("struct V3AccountSettings: View {",1)[1].split(
            "\nstruct V3BoolSettingRow: View {",1)[0]
        self.assertIn('Button("Test local settings button") {',view)
        self.assertIn("localTouchEvents += 1",view)
        self.assertIn('Text("Local touch events: \\(localTouchEvents)")',view)
        self.assertIn("ScarletV183HostLog.record(.settingsLocalTouch)",view)
        action=view.split('Button("Test local settings button") {',1)[1].split("}",1)[0]
        self.assertNotIn("V3ServiceBridge",action)
        self.assertNotIn("status.",action)

    def test_all_existing_sections_remain_and_no_duplicate_overlay(self):
        view=self.out.split("struct V3AccountSettings: View {",1)[1].split(
            "\nstruct V3BoolSettingRow: View {",1)[0]
        for item in ('Section("Setup")','Section("Account and Signing")',
                     'Section("Device")','Section("Apps and Data")',
                     'Section("Services")','Section("Diagnostics")','Section("Guest Runtime")'):
            self.assertIn(item,view)
        self.assertEqual(view.count('Section("Settings Controls Diagnostic")'),1)
        self.assertEqual(SOURCE.count('struct V3AccountSettings: View'),1)
        self.assertEqual(self.out.count('struct V3AccountSettings: View'),1)
        self.assertEqual(SOURCE.count("client.v3Execute(data)"),self.out.count("client.v3Execute(data)"))

    def test_service_toggle_is_disabled_and_retry_is_visible(self):
        out=self.out.split("struct V3BoolSettingRow: View {",1)[1].split(
            "\nprivate struct V3SourceAddFailure",1)[0]
        self.assertIn(".disabled(status.isStale || !loaded || loadingRequest)",out)
        self.assertIn('Button("Retry SideStore settings")',out)
        self.assertIn("ScarletV183HostLog.record(.settingsSideStoreRetry)",out)
        self.assertIn('requestDeadline: Date().addingTimeInterval(15)',out)
        self.assertIn('Settings could not be read from SideStore',out)

    def test_missing_boolean_reply_does_not_become_false_success(self):
        out=self.out.split("struct V3BoolSettingRow: View {",1)[1].split(
            "\nprivate struct V3SourceAddFailure",1)[0]
        before,after=out.split("            } else {\n                // A reply without an authoritative value",1)
        self.assertIn("loaded = true",before)
        self.assertIn("loaded = false",after)
        self.assertIn("loadFailure = true",after)
        self.assertIn("settingsToggleReadFailed",after)
        self.assertNotIn("status.settings[key] ?? false",out)

    def test_local_host_controls_do_not_depend_on_app_group_or_service(self):
        source=mod.patch_settings(LOCAL_SETTINGS)
        self.assertEqual(source,mod.patch_settings(source))
        self.assertIn("ScarletV183HostLog.record(.settingsLocalClearNotifications)",source)
        self.assertIn("removeAllPendingNotificationRequests",source)
        self.assertEqual(self.out,mod.patch_shell(self.out))

    def test_source_drift_fails_before_side_effect(self):
        with self.assertRaises(ValueError):
            mod.patch_shell(SHELL.replace('Section("Setup")','Section("Missing Setup")'))
        with self.assertRaises(ValueError):
            mod.patch_shell(SOURCE)
        with self.assertRaises(ValueError):
            mod.patch_settings(LOCAL_SETTINGS.replace("clearNotifications","renamed"))


if __name__=="__main__":
    unittest.main()
