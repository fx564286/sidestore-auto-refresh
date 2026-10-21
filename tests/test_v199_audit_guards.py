"""Source contracts for V199 full CI test gate and Keychain diagnostic deduplication."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V199AuditGuards(unittest.TestCase):
    def test_ci_runs_full_tests_with_exact_skip_allowlist(self):
        workflow = (ROOT / ".github/workflows/livecontainer-build.yml").read_text()
        start = workflow.index("- name: Run repository checks before patches")
        end = workflow.index("\n      - name:", start + 3)
        checks = workflow[start:end]
        self.assertIn("builder/scripts/run_required_tests.py", checks)
        self.assertIn("--pattern 'test_*.py'", checks)
        self.assertIn("builder/scripts/required_test_skip_allowlist.json", checks)
        self.assertNotIn("for pattern in", checks)
        self.assertIn("set -euo pipefail", checks)
        self.assertIn("2>&1 | tee artifacts/logs/repository-tests.log", checks)

    def test_keychain_success_log_is_deduplicated_without_suppressing_errors(self):
        source = (ROOT / "scripts/templates/embedded_shared_keychain.swift").read_text()
        marker = "private static func recordAuthenticationSnapshotIssue(_ status: Int)"
        self.assertEqual(source.count(marker), 1)
        body = source[source.index(marker):].split("\n    static func authenticationFailure", 1)[0]
        self.assertIn("snapshotLogLock.lock()", body)
        self.assertIn("snapshotLogLock.unlock()", body)
        self.assertIn("let shouldLog = status != 0 || !snapshotSuccessLogged", body)
        self.assertIn("snapshotSuccessLogged = status == 0", body)
        self.assertIn("guard shouldLog else { return }", body)
        self.assertIn("[LC_KEYCHAIN] SNAPSHOT status=", body)
        self.assertIn("recordAuthenticationSnapshotIssue(error.code)", source)
        self.assertIn("recordAuthenticationSnapshotIssue(snapshot == nil ? -25300 : 0)", source)


if __name__ == "__main__":
    unittest.main()
