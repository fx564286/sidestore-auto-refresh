"""NRG V26 regression checks for cancellation provenance without secrets."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CancellationOriginRegression(unittest.TestCase):
    def test_backend_watchdog_and_user_cancel_are_distinct(self):
        runtime=(ROOT/"scripts/templates/v3_headless_runtime.swift").read_text()
        self.assertIn("source=operation_watchdog",runtime)
        self.assertIn("source=operation_cancel",runtime)
        self.assertIn("last_pipeline_phase=",runtime)
        self.assertIn("cancellation_requested=",runtime)
        self.assertIn('"failure": failure.wire',runtime)

    def test_ui_disappearance_is_explicitly_diagnosed(self):
        shell=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text()
        sheet=shell[shell.index("struct V3OperationSheet"):shell.index("struct V3PromptSection")]
        self.assertIn("[NRG_V26_UI_COVER]",sheet)
        self.assertIn('V3ServiceBridge.shared.request(operation: "opCancel"',sheet)

    def test_patch_is_bounded_and_never_disables_user_cancel(self):
        patch=(ROOT/"scripts/patch_v26_install_trace.py").read_text()
        self.assertIn("NRG_V26_PIPELINE_STEP",patch)
        self.assertIn("NRG_V26_PARENT_TASK",patch)
        self.assertIn("NRG_V26_DOWNLOAD_TERMINAL",patch)
        self.assertIn('if "NRG_V24_INSTALL_DOWNLOAD_RECOVERY" not in texts[downloader]',patch)
        self.assertNotIn("cancel() = {}",patch)
        self.assertNotIn("task.cancel = ",patch)
        self.assertNotIn("try! await",patch)
        self.assertNotIn('debugLog("\\(downloadURL)',patch)
        self.assertNotIn('debugLog("\\(error)',patch)

if __name__=="__main__":
    unittest.main()
