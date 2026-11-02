"""V170: refresh callback preserves structured failures and logs only envelope metadata."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts/templates/combined_refresh_handler.swift"

class RefreshEnvelopeDiagnostics(unittest.TestCase):
    def test_failure_envelope_fallback_is_explicit_and_safe(self):
        source = TEMPLATE.read_text(encoding="utf-8")
        marker = "// SCARLET_V170_REFRESH_ENVELOPE_DIAG:"
        self.assertEqual(source.count(marker), 1)
        self.assertIn('CombinedFailure.fromEncodedString(error, expectedID: runID)', source)
        self.assertIn('decodedFailure ??\n                CombinedFailure(operation: "refresh", stage: .command, id: runID)', source)
        for token in ('encoder_failed', 'structured_invalid_or_mismatched',
                      'legacy_or_unstructured', 'decoded=%d classified=%d'):
            self.assertIn(token, source)
        log = next(line for line in source.splitlines()
                   if '[SCARLET_V170_REFRESH_ENVELOPE] run_id=' in line)
        self.assertNotIn('error=%@', log)
        self.assertNotIn('message=%@', log)
        self.assertNotIn('raw=%@', log)

    def test_refresh_wire_validity_not_weakened(self):
        failure = (ROOT / "scripts/templates/combined_failure.swift").read_text(encoding="utf-8")
        self.assertIn('uuidCorrelationMatches(value["correlationID"] as? String, expectedID: expectedID)', failure)
        self.assertIn('text.hasPrefix("LCFAILURE1:")', failure)

if __name__ == "__main__":
    unittest.main()
