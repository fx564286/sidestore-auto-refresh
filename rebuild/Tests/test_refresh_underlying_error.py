from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PANEL = (ROOT / "HostApp/ScarletSigningReadinessPanel.swift").read_text()
RECORDER = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()

class RefreshErrorEvidence(unittest.TestCase):
    def test_real_underlying_error_captured_without_message(self):
        self.assertIn('"manual_request_underlying_error", error: error', PANEL)
        self.assertIn('func recordError(_ category: String', RECORDER)
        self.assertIn('"domain": code.domain, "code": String(code.code)', RECORDER)
        self.assertIn('"entitled_app_group"', RECORDER)
        self.assertIn('"group_accessible"', RECORDER)
        self.assertIn('"lc_cert_present"', RECORDER)

if __name__ == "__main__": unittest.main()
