from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PANEL = (ROOT / "HostApp/ScarletSigningReadinessPanel.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
RECORDER = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()

class RefreshErrorEvidence(unittest.TestCase):
    def test_real_underlying_error_captured_without_message(self):
        self.assertIn('"manual_request_underlying_error", error: error', PANEL)
        self.assertIn('func recordError(_ category: String', RECORDER)
        self.assertIn('"domain": code.domain, "code": String(code.code)', RECORDER)
        self.assertIn('"entitled_app_group"', RECORDER)
        self.assertIn('"group_accessible"', RECORDER)
        self.assertIn('"lc_cert_present"', RECORDER)

    def test_signature_failure_reports_real_code_and_postcheck_failure(self):
        self.assertIn('LCUtils.validateJITLessSetup { verified, validationError in', HOST)
        self.assertIn('"jitless_probe_underlying_error"', HOST)
        self.assertIn('"signature_postcheck_invalid"', HOST)

if __name__ == "__main__": unittest.main()
