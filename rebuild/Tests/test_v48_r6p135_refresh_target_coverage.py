"""R135 native result coverage: regression contract plus executable Swift fixture."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

R = Path(__file__).resolve().parents[1]
S = (R / "integration/ScarletGuestRefreshAgent.swift.txt").read_text()
X = (R / "HostApp/ScarletAuthXPCSupport.swift").read_text()
A = (R / "HostApp/ScarletAutomaticRenewal.swift").read_text()

class RefreshTargetCoverage(unittest.TestCase):
    def test_capture_before_dispatch_and_check_before_success(self):
        self.assertIn("let expectedTargetIDs = await context.perform", S)
        self.assertIn("Set(targets.map { $0.bundleIdentifier })", S)
        start = S.index("let expectedTargetIDs = await context.perform")
        dispatch = S.index("AppManager.shared.refresh(", start)
        coverage = S.index("ScarletRefreshTargetCoverage.failure(", dispatch)
        success = S.index('reply(true, "native_selected_team_refresh_returned_install_unverified")', coverage)
        self.assertLess(start, dispatch)
        self.assertLess(dispatch, coverage)
        self.assertLess(coverage, success)
        self.assertIn("reply(false, coverageFailure)", S[coverage:success])

    def test_finite_reason_survives_xpc_and_guidance(self):
        for reason in ("selected_team_partial_refresh_results",
                       "selected_team_refresh_result_mismatch"):
            self.assertIn('"' + reason + '"', X)
            self.assertIn('case "' + reason + '":', A)

    def test_actual_swift_set_coverage(self):
        swift = shutil.which("swift")
        if not swift:
            self.skipTest("Swift unavailable on this host; Xcode CI can execute fixture")
        self.assertIn("private enum ScarletRefreshTargetCoverage", S)
        helper = "private enum ScarletRefreshTargetCoverage" + S.split(
            "private enum ScarletRefreshTargetCoverage", 1)[1].split(
            "@objc(ScarletGuestRefreshAgent)", 1)[0]
        cases = """
precondition(ScarletRefreshTargetCoverage.failure(expected: ["a", "b"], returned: ["b", "a"], host: "a") == nil)
precondition(ScarletRefreshTargetCoverage.failure(expected: ["a", "b"], returned: ["a"], host: "a") == "selected_team_partial_refresh_results")
precondition(ScarletRefreshTargetCoverage.failure(expected: ["a", "b"], returned: ["b"], host: "a") == "host_not_in_refresh_results")
precondition(ScarletRefreshTargetCoverage.failure(expected: ["a"], returned: [], host: nil) == "selected_team_not_in_refresh_results")
precondition(ScarletRefreshTargetCoverage.failure(expected: ["a"], returned: ["a", "foreign"], host: nil) == "selected_team_refresh_result_mismatch")
precondition(ScarletRefreshTargetCoverage.failure(expected: ["a"], returned: ["foreign"], host: nil) == "selected_team_refresh_result_mismatch")
precondition(ScarletRefreshTargetCoverage.failure(expected: ["a"], returned: ["a"], host: nil) == nil)
print("R135_REFRESH_COVERAGE_PASS")
"""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "main.swift"
            f.write_text(helper + cases)
            p = subprocess.run([swift, "-swift-version", "6", str(f)],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("R135_REFRESH_COVERAGE_PASS", p.stdout)

if __name__ == "__main__":
    unittest.main()
