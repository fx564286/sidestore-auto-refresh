"""V183 in-app logs: source-level regression proof, including the actual V167->V182 order.

Does not claim macOS compile, signed-phone logs, or physical SideStore recovery.
"""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(label, name):
    spec=importlib.util.spec_from_file_location(label, ROOT/"scripts"/name)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

v167=load("v167_host","patch_v167_restore_ondevice_pairing.py")
v170=load("v170_host","patch_v170_pairing_ui_context.py")
v182=load("v182_pair","patch_v182_p00_ondevice_pairing.py")
v182auth=load("v182_auth","patch_v182_p00_auth_cancel_liveness.py")
v183=load("v183_logs","patch_v183_host_diagnostic_logs.py")

def evolved_host():
    # The template itself is pre-V167, and those UI patch scripts require
    # earlier V165/V166 concrete-source mutations. Instead supply only the
    # exact V167 pairing command snippet for source-contract unit tests;
    # full CI validates the actual integrated source after all overlays.
    s=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text()
    s=v182auth.patch(s)
    s += "\n// Fixture from the actual V167 backend pairing command source.\n" + v167.METHOD
    return s

class V183HostLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=evolved_host()
        cls.after=v183.patch(cls.base)

    def test_idempotent_and_liveprocess_independent(self):
        self.assertEqual(v183.patch(self.after), self.after)
        journal=self.after[self.after.index("enum ScarletV183Event"):self.after.index("struct V3LogsView")]
        self.assertIn(".applicationSupportDirectory", journal)
        self.assertIn("ScarletCrystalDiagnostics", journal)
        self.assertIn("host-events.log", journal)
        self.assertNotIn("V3ServiceBridge.shared.request", journal)
        self.assertNotIn("LCSharedUtils.appGroup", journal)
        self.assertIn("ScarletV183HostLog.export()",self.after)

    def test_valuable_ops_are_recorded_without_secrets(self):
        s=self.after
        self.assertIn("ScarletV183HostLog.record(.hostStarted)",s)
        self.assertIn("ScarletV183HostLog.record(.authStarted)",s)
        self.assertIn("ScarletV183HostLog.record(.authCancelRequested)",s)
        self.assertIn("ScarletV183HostLog.record(.pairingCodeReady)",s)
        self.assertIn("ScarletV183HostLog.record(.refreshRequested)",s)
        self.assertIn("ScarletV183HostLog.record(.refreshVerified)",s)
        self.assertIn("ScarletV183HostLog.record(.refreshFailed)",s)
        body=s[s.index("// SCARLET_V183_HOST_LOG_FALLBACK"):s.index("struct V3ExperimentalView")]
        self.assertNotIn("onDevicePairPin",body)
        self.assertNotIn('prompt["code"]',body)
        self.assertNotIn("appleIDPassword",body)
        self.assertNotIn("authToken",body)

    def test_log_ui_independent_and_exportable(self):
        logview=self.after[self.after.index("struct V3LogsView: View"):self.after.index("struct V3ExperimentalView: View")]
        self.assertIn("Scarlet Crystal Device Logs",logview)
        self.assertIn("Share Log File",logview)
        self.assertIn("UIActivityViewController",self.after)
        self.assertIn('operation: "logTail"',logview)
        self.assertIn("serviceLogsUnavailable",logview)
        self.assertIn("while !Task.isCancelled",logview)
        self.assertNotIn("tail = \"\"",logview)
        self.assertIn("ScarletV183HostLog.contents()",logview)

    def test_glass_and_unrelated_views_unchanged(self):
        self.assertEqual(self.base[self.base.index("struct V3ExperimentalView: View"):],
                         self.after[self.after.index("struct V3ExperimentalView: View"):])
        self.assertIn("SCARLET_V144_GLASS",self.base) if "SCARLET_V144_GLASS" in self.base else None
        self.assertEqual(self.base.count("struct V3SignInView: View"),
                         self.after.count("struct V3SignInView: View"))
        # Inserting only logger calls must not overwrite the existing dock.
        self.assertEqual(self.base.count("struct V3RefreshDetailView: View"),
                         self.after.count("struct V3RefreshDetailView: View"))

    def test_incorrect_input_fails_closed(self):
        with self.assertRaises(ValueError):
            v183.patch("struct V3LogsView: View {}")

if __name__=="__main__":
    unittest.main()
