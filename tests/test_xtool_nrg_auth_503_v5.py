"""Offline tests for isolated hsc434 replay HTTP 503 recovery.

Verify it cannot retry password proofs, app tokens, 2FA, generic login errors,
or modify Anisette provisioned identity, certificates, or signed apps.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sp = importlib.util.spec_from_file_location(
    "nrg_xtool_auth_503_v5", ROOT/"scripts"/"xtool_nrg_auth_503_v5.py"
)
v5 = importlib.util.module_from_spec(sp)
sp.loader.exec_module(v5)


class Xtool503RecoveryV5Tests(unittest.TestCase):
    def test_idempotent_exact_source_and_drift_fails_closed(self):
        old = "x " + v5.MARKER.replace("503_V5", "HSC434_V4") + "\n" + v5.OLD
        updated = v5.transform(old)
        self.assertEqual(v5.transform(updated), updated)
        self.assertEqual(updated.count(v5.MARKER), 1)
        with self.assertRaises(ValueError):
            v5.transform("source from another xtool release")

    def test_only_after_hsc434_resync_not_password_or_2fa(self):
        src = v5.NEW
        self.assertIn("adi.nrgResync(sim: sim)", src)
        self.assertIn("anisette_resync=completed", src)
        self.assertIn("for index in 0..<3", src)
        self.assertIn("replayHTTP.status.code == 503 && index < 2", src)
        self.assertIn("2_000_000_000", src)
        self.assertIn("5_000_000_000", src)
        for forbidden in ("GrandSlamAuthCompleteRequest", "GrandSlamAppTokensRequest",
                          "GrandSlamValidateRequest", "reprovision(", "resetProvisioning("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)

    def test_trace_never_logs_credential_sim_or_request_body(self):
        src = v5.NEW
        self.assertIn("phase=anisette_resync",src)
        self.assertIn("apple_replay_http=503",src)
        self.assertNotIn("print(sim)",src)
        self.assertNotIn("print(refreshed)",src)
        self.assertNotIn("print(httpRequest)",src)
        self.assertNotIn("print(retryBody)",src)

    def test_exact_source_changes_only_one_swift_file(self):
        self.assertEqual(v5.TARGET.as_posix(),
            "Sources/XKit/GrandSlam/GrandSlamClient.swift")


if __name__ == "__main__":
    unittest.main()
