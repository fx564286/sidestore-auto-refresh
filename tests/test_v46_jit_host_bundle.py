#!/usr/bin/env python3
"""Pinned-source contract tests for Madeira -> StikDebug -> LiveContainer return."""
import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jit_host", ROOT / "scripts/patch_v46_jit_host_bundle.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class JITHostReturnTests(unittest.TestCase):
    def test_normalization_is_scoped_to_liveprocess_and_entitlement(self):
        patched = module.patch(module.ORIGINAL)
        self.assertIn('if (isLiveProcess && [expectedBundleId hasSuffix:@".LiveProcess"])', patched)
        self.assertIn('expectedBundleId.length - @".LiveProcess".length', patched)
        self.assertIn("[LC_JIT_HANDOFF]", patched)
        self.assertEqual(patched.count(module.MARKER), 1)

    def test_guest_bundle_override_remains_opt_in(self):
        source = 'if([guestAppInfo[@"doUseLCBundleId"] boolValue] ) {\n' + module.ORIGINAL + '\n}'
        changed = module.patch(source)
        self.assertTrue(changed.startswith('if([guestAppInfo[@"doUseLCBundleId"] boolValue] ) {'))
        self.assertIn('if(![infoPlist[@"CFBundleIdentifier"] isEqualToString:expectedBundleId])', changed)

    def test_upstream_drift_fails_closed(self):
        with self.assertRaises(RuntimeError):
            module.patch("unrecognized bootstrap")
        with self.assertRaises(RuntimeError):
            module.patch(module.ORIGINAL + module.ORIGINAL)
        with self.assertRaises(RuntimeError):
            module.patch(" // " + module.MARKER)

    def test_pinned_bootstrap_and_repeated_application(self):
        checkout = os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not checkout:
            self.skipTest("pinned LiveContainer unavailable")
        source = subprocess.check_output([
            "git", "-C", checkout, "show",
            "12377cf3b91d51739a33f14a302e5f522b238593:" + str(module.TARGET),
        ], text=True)
        changed = module.patch(source)
        self.assertEqual(changed, module.patch(changed))
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / module.TARGET
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source)
            module.main(Path(temp))
            once = target.read_bytes()
            module.main(Path(temp))
            self.assertEqual(target.read_bytes(), once)

if __name__ == "__main__":
    unittest.main()
