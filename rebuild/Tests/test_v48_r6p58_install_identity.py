"""R6P58: versioned host identity without changing original app or guest data."""
from pathlib import Path
import ast
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/"integration/package_paired.py"
WF=ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml"

spec=importlib.util.spec_from_file_location("scarlet_package_p58",PKG)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class R6P58HostIdentity(unittest.TestCase):
    def test_advances_build_but_keeps_existing_identity_and_data(self):
        info={"CFBundleIdentifier":"com.kdt.livecontainer.P8EZT3U5N4",
              "CFBundleVersion":"3.8.11",
              "CFBundleShortVersionString":"3.8.11",
              "CFBundleDisplayName":"Scarlet Crystal",
              "ALTAppGroups":["group.com.SideStore.SideStore"]}
        module.apply_host_build_version(info,"3.8.58")
        self.assertEqual(info["CFBundleVersion"],"3.8.58")
        self.assertEqual(info["CFBundleShortVersionString"],"3.8.11")
        self.assertEqual(info["CFBundleIdentifier"],module.HOST_ID)
        self.assertEqual(info["ALTAppGroups"],["group.com.SideStore.SideStore"])

    def test_refuses_stale_or_downgraded_build_numbers(self):
        for value in ("3.8.11","3.8.10","3.7.999","bad","1.2.3.4",""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.apply_host_build_version({"CFBundleVersion":"3.8.11"},value)

    def test_previous_builds_keep_compatibility_when_not_explicit(self):
        info={"CFBundleVersion":"3.8.11"}
        module.apply_host_build_version(info,None)
        self.assertEqual(info["CFBundleVersion"],"3.8.11")

    def test_native_workflow_builds_and_checks_distinct_p58_identity(self):
        source=WF.read_text()
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.58)',source)
        self.assertIn('SCARLET_HOST_VERSION_ARGS[@]',source)
        self.assertIn('info["CFBundleVersion"]=="3.8.58"',source)
        self.assertIn('info["CFBundleIdentifier"]=="com.kdt.livecontainer.P8EZT3U5N4"',source)
        self.assertIn('scarlet-v48-r6p58-install-identity-unsigned-20261114',source)
        self.assertIn('Scarlet-Crystal-V48-R6P58-INSTALL-IDENTITY-UNSIGNED.ipa',source)
        ast.parse(PKG.read_text())

if __name__=="__main__":
    unittest.main()
