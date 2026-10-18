#!/usr/bin/env python3
"""V46 JIT route regression using the exact pinned SideStore sources."""
import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

repair = load(ROOT / "scripts/patch_v46_jit_recovery.py", "jit_repair")
guard = load(ROOT / "scripts/patch_v43_sidejit_dns_guard.py", "jit_guard")
PIN = "ff25922e5c13ccfafd83bda5092910d848ebd409"

class JITRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get("EMBEDDED_SIDESTORE_TEST_SOURCE", ROOT / "work/EmbeddedSideStore"))
        if not cls.source.is_dir():
            raise unittest.SkipTest("pinned SideStore checkout not available")

    def pinned(self, relative):
        return subprocess.check_output(
            ["git", "-C", str(self.source), "show", f"{PIN}:{relative}"], text=True
        )

    def test_dns_descriptor_fails_closed_and_valid_override_preserved(self):
        first = guard.patch(self.pinned(repair.MANAGER))
        code = repair.patch_manager(first)
        self.assertIn("return nil", code)
        self.assertIn("NRG_V43_DNSSD_FAIL_CLOSED", code)
        self.assertIn("return resolved", code)  # valid custom server survives
        self.assertIn('return "" // NRG_V44 unresolved override', code)
        self.assertIn("unresolved .local names must not be returned", code)
        self.assertIn('["http", "https"].contains(scheme)', code)
        self.assertEqual(repair.patch_manager(code), code)

    def test_missing_helper_falls_back_to_debugapp(self):
        code = repair.patch_operation(self.pinned(repair.OPERATION))
        self.assertIn("guard !sideJITURLString.isEmpty", code)
        self.assertIn("try await debugApp(targetBundleId)", code)
        self.assertIn("[NRG_JIT] external server unavailable", code)
        self.assertIn("[NRG_JIT] SideJIT transport failed", code)
        self.assertIn("case .timedOut, .cannotFindHost, .cannotConnectToHost", code)
        self.assertEqual(repair.patch_operation(code), code)

    def test_server_error_never_returns_false_success(self):
        code = repair.patch_operation(self.pinned(repair.OPERATION))
        self.assertIn("let (data, response) = try await URLSession.shared.data(for: request)", code)
        self.assertIn("(200...299).contains(http.statusCode)", code)
        self.assertIn('throw SideJITServerErrorType.other("SideJITServer HTTP', code)
        self.assertIn('throw OperationError.SideJITIssue(error: message)', code)
        self.assertLess(code.index("guard let http"), code.index('if cleanString.contains("Enabled JIT for")'))
        self.assertEqual(repair.patch_operation(code), code)

    def test_atomic_fail_closed_source_drift(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            a = path / repair.MANAGER
            b = path / repair.OPERATION
            a.parent.mkdir(parents=True, exist_ok=True)
            b.parent.mkdir(parents=True, exist_ok=True)
            a.write_text(guard.patch(self.pinned(repair.MANAGER)))
            b.write_text("unexpected upstream source")
            before = a.read_bytes()
            with self.assertRaises(RuntimeError):
                repair.main(path)
            self.assertEqual(a.read_bytes(), before)

    def test_pinned_transform_and_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            for rel in (repair.MANAGER, repair.OPERATION):
                f = path / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                value = self.pinned(rel)
                if rel == repair.MANAGER:
                    value = guard.patch(value)
                f.write_text(value)
            repair.main(path)
            initial = {str(p): (path / p).read_bytes() for p in (repair.MANAGER, repair.OPERATION)}
            repair.main(path)
            self.assertEqual(initial, {str(p): (path / p).read_bytes() for p in (repair.MANAGER, repair.OPERATION)})

if __name__ == "__main__":
    unittest.main()
