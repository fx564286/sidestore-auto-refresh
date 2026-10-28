"""Regression tests for fast CI identity and release safety gate."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("scarlet_ci_preflight",
                                           ROOT/"scripts"/"scarlet_ci_preflight.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CIPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow=(ROOT/module.WORKFLOW).read_text()
        cls.packager=(ROOT/module.PACKAGER).read_text()

    def test_real_workflow(self):
        self.assertEqual(module.verify(self.workflow,self.packager,ROOT),
                         ("3.8.228","V155"))

    def test_stale_label_fails_before_xcode(self):
        broken=self.workflow.replace(
            "grep -Fq '<string>V155</string>' work/LiveContainer/LiveContainer/Info.plist",
            "grep -Fq '<string>V154</string>' work/LiveContainer/LiveContainer/Info.plist")
        self.assertNotEqual(broken,self.workflow)
        with self.assertRaisesRegex(module.PreflightError,"stale Info.plist label"):
            module.verify(broken,self.packager,ROOT)

    def test_package_version_mismatch_fails(self):
        broken=self.packager.replace("if version == '3.8.228' and build_label != 'V155'",
                                    "if version == '3.8.228' and build_label != 'V154'")
        self.assertNotEqual(broken,self.packager)
        with self.assertRaisesRegex(module.PreflightError,"packager version"):
            module.verify(self.workflow,broken,ROOT)

    def test_archival_validation_is_required(self):
        broken=self.workflow.replace(
            "name: V78 Gate 1 unsigned archive and Mach-O verification",
            "name: skipped archive")
        with self.assertRaisesRegex(module.PreflightError,"archive verification"):
            module.verify(broken,self.packager,ROOT)

    def test_release_suite_cannot_disappear(self):
        broken=self.workflow.replace(
            "name: Run repository checks before patches",
            "name: tests disabled")
        with self.assertRaisesRegex(module.PreflightError,"release full suite"):
            module.verify(broken,self.packager,ROOT)

    def test_branch_isolation_and_fast_release_profiles(self):
        s=self.workflow
        self.assertIn("livecontainer-",s)
        self.assertIn("github.ref",s)
        self.assertIn("SCARLET_CI_PROFILE: ",s)
        self.assertIn("env.SCARLET_CI_PROFILE == 'release'",s)
        self.assertIn("default: release",s)
        self.assertIn("- fast",s)
        self.assertIn("- release",s)
        self.assertNotIn("ci/scarlet-quality-speed-20261028",s)

if __name__ == "__main__":
    unittest.main()
