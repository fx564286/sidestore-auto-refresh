"""P102 regression: identify portal failures + zero-target reasons without touching P101 signer."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = (ROOT / "rebuild/integration/ScarletGuestSavedAccounts.swift.txt").read_text()
REFRESH = (ROOT / "rebuild/integration/ScarletGuestRefreshAgent.swift.txt").read_text()
HOST = (ROOT / "rebuild/HostApp/ScarletAuthXPCSupport.swift").read_text()
DIAG = (ROOT / "rebuild/HostApp/ScarletDiagnosticRecorder.swift").read_text()
GUIDANCE = (ROOT / "rebuild/HostApp/ScarletAutomaticRenewal.swift").read_text()
STATUS = (ROOT / "rebuild/HostApp/ScarletFullscreenSceneStack.swift").read_text()

class P102PortalAndRefresh(unittest.TestCase):
    def test_p101_guest_signing_stays_out_of_scope(self):
        self.assertIn("candidate_not_in_host_profile",
                      (ROOT / "rebuild/HostApp/ScarletIntegratedHostView.swift").read_text())
        self.assertIn("nativeStatusBarCollisionShield", STATUS)
        self.assertIn("if unsafe > 0", STATUS)

    def test_portal_stage_errors_are_not_flattened(self):
        self.assertIn('portalFailure(error, stage: "preflight")', NATIVE)
        self.assertIn('portalFailure(error, stage: "create", reason: fallback)', NATIVE)
        self.assertIn('portalFailure(error, stage: "readback",', NATIVE)
        self.assertIn('portalFailure(error, stage: "import_lookup")', NATIVE)
        self.assertIn("deepest.userInfo[NSUnderlyingErrorKey]", NATIVE)
        helper = NATIVE.split("private static func portalFailure(", 1)[1].split(
            "// P89: SideInstaller", 1)[0]
        for forbidden in ("localizedDescription", "debugDescription", "password",
                          "token", "requestURL", "absoluteString", "appleID"):
            self.assertNotIn(forbidden, helper)
        self.assertIn('"selected_team_certificate_quota_reached"', helper)
        self.assertIn('scarlet_certificate_failure:', helper)
        # Force-fresh path still cannot pass through cached certificate reuse.
        self.assertIn('if !forceNew {', NATIVE)
        self.assertIn('if forceNew && previouslyRegistered.contains(', NATIVE)
        self.assertNotIn("revokeCertificate(", NATIVE)

    def test_host_logs_structured_error_without_unbounded_strings(self):
        self.assertIn("ScarletCertificatePortalEvidence.decode(raw)", HOST)
        self.assertIn('"native_issue_portal_error_evidence"', HOST)
        self.assertIn("known.contains(reason) ? reason : \"worker_unknown\"", HOST)
        self.assertIn("allowedReasons.contains(item.reason)", HOST)
        self.assertIn("domains.contains(item.underlyingDomain)", HOST)
        self.assertIn('"native_error_stage"', DIAG)
        self.assertIn('"native_underlying_code"', DIAG)

    def test_zero_targets_separates_inactive_excluded_and_missing(self):
        self.assertIn('fetchAppsForRefreshingAll(in: context)', REFRESH)
        self.assertIn("context.fetch(InstalledApp.fetchRequest())", REFRESH)
        self.assertIn("owned.allSatisfy { !$0.isActive }", REFRESH)
        self.assertIn("managed_apps_inactive_for_selected_team", REFRESH)
        self.assertIn("managed_apps_excluded_from_refresh_for_selected_team", REFRESH)
        self.assertIn("selected_team_inventory_unavailable", REFRESH)
        self.assertIn("no_managed_apps_for_selected_team", REFRESH)
        for reason in ("managed_apps_inactive_for_selected_team",
                       "managed_apps_excluded_from_refresh_for_selected_team",
                       "selected_team_inventory_unavailable"):
            self.assertIn(f'"{reason}"', HOST)
            self.assertIn(f'case "{reason}":', GUIDANCE)

    def test_real_decoder_rejects_private_payload_fields(self):
        swift = shutil.which("swift")
        if not swift:
            self.skipTest("Swift runtime unavailable; run native decoder in Xcode CI")
        decoder = HOST.split("public struct ScarletCertificatePortalEvidence:", 1)[1].split(
            "// R6P66_MULTI_ACCOUNT_TRANSPORT_BEGIN", 1)[0]
        valid = dict(v=1, reason="selected_team_certificate_portal_failed",
                     stage="create", domain="appleapi", code=7460,
                     underlyingDomain="url", underlyingCode=-1009, depth=1)
        samples = [("scarlet_certificate_failure:" + json.dumps(valid), True)]
        for key, value in [
            ("v", 2), ("stage", "password"), ("domain", "apple@example.com"),
            ("reason", "secret"), ("code", 2147483648), ("depth", 7),
            ("underlyingDomain", "secret"), ("underlyingCode", -2147483649)
        ]:
            test = dict(valid); test[key] = value
            samples.append(("scarlet_certificate_failure:" + json.dumps(test), False))
        samples.extend([("scarlet_certificate_failure:{", False),
                        ("scarlet_certificate_failure:" + "a"*1200, False)])
        code = "import Foundation\\npublic struct ScarletCertificatePortalEvidence:" + decoder
        for value, expected in samples:
            code += "precondition((ScarletCertificatePortalEvidence.decode(" + json.dumps(value) +                     ") != nil) == " + str(expected).lower() + ")\\n"
        code += 'print("P102_DECODER_PASS")\\n'
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"main.swift";f.write_text(code.replace("\\n", "\n"))
            proc=subprocess.run([swift, str(f)],capture_output=True,text=True,timeout=120)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn("P102_DECODER_PASS",proc.stdout)

if __name__ == "__main__":
    unittest.main()
