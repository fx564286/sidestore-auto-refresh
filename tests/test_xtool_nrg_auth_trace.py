"""Offline checks for isolated xtool 1.22.2 GrandSlam phase trace.

No network activity, passwords, Apple requests or authenticator state required.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "xtool_nrg_auth_trace", ROOT / "scripts" / "xtool_nrg_auth_trace.py"
)
trace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trace)


class NRGXtoolAuthTraceTests(unittest.TestCase):
    def source(self):
        return (
            'import Foundation\n'
            'NRG_XTOOL_SIDESTORE_AUTH_V1\n'
            + trace.OLD
            + '\n'
            + trace.OLD_RESPONSE
        )

    def test_trace_replacement_is_idempotent(self):
        transformed = trace.transform(self.source())
        self.assertEqual(trace.transform(transformed), transformed)
        self.assertEqual(transformed.count(trace.MARKER), 1)

    def test_unknown_source_or_partial_patch_fails_closed(self):
        with self.assertRaises(ValueError):
            trace.transform("a non-pinned version of xtool")
        with self.assertRaises(ValueError):
            trace.transform(self.source() + "NRG_XTOOL_AUTH_TRACE_V2")

    def test_only_phase_http_and_typed_code_can_be_logged(self):
        changed = trace.transform(self.source())
        for phase in ("init", "complete", "apptokens", "2fa_validate", "2fa_trusted"):
            with self.subTest(phase=phase):
                self.assertIn(f'phase = "{phase}"', changed)
        self.assertIn('NRG_XTOOL_AUTH_TRACE', changed)
        self.assertIn('GrandSlamOperationError', changed)
        self.assertIn('HTTPResponseError', changed)
        self.assertIn("error.status.code", changed)
        self.assertNotIn("error.localizedDescription", changed)
        self.assertNotIn("String(data: resp.body", changed)
        self.assertNotIn('print(resp.body)', changed)
        self.assertNotIn('print(httpRequest)', changed)
        self.assertNotIn('print(anisetteData)', changed)
        self.assertNotIn('print(deviceInfo)', changed)

    def test_opt_in_environment_is_explicit(self):
        changed = trace.transform(self.source())
        self.assertIn('DeviceInfo.nrgSideStoreAuth', changed)
        self.assertIn('["NRG_XTOOL_AUTH_TRACE"] == "1"', changed)


if __name__ == "__main__":
    unittest.main()
