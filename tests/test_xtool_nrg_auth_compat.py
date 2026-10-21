"""Offline contract checks for the opt-in NRG/SideInstaller xtool auth bridge.

No credentials, Apple API requests, certificates, or iOS device operations.
"""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "xtool_nrg_auth_compat", HERE / "scripts" / "xtool_nrg_auth_compat.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class NRGXtoolAuthCompatibilityTests(unittest.TestCase):
    def test_every_patch_is_idempotent(self):
        for path, replacements in mod.PATCHES.items():
            with self.subTest(path=path):
                upstream = "\n".join(before for before, _ in replacements)
                after = mod.patched(upstream, replacements, path)
                self.assertEqual(mod.patched(after, replacements, path), after)
                self.assertIn(mod.MARKER, after)

    def test_anchor_drift_fails_closed(self):
        with self.assertRaises(ValueError):
            mod.patched("unexpected source", [("required upstream anchor", "replacement")], "fixture.swift")

    def test_only_isolated_opt_in_auth_state(self):
        device = str(mod.PATCHES["Sources/XKit/GrandSlam/Anisette/DeviceInfo.swift"])
        directory = str(mod.PATCHES["Sources/XKit/Utilities/DirectoryProvider.swift"])
        self.assertIn("NRG_XTOOL_SIDESTORE_AUTH", device)
        self.assertIn("NRG_XTOOL_COMPAT_STATE", device)
        self.assertIn('hasPrefix("/")', device)
        self.assertIn("NRG_XTOOL_COMPAT_STATE", directory)

    def test_no_signing_or_deletion_apis(self):
        source = (HERE / "scripts" / "xtool_nrg_auth_compat.py").read_text()
        for forbidden in ("revokeCertificate(", "deleteAppID(", "uninstall(", "signInPlace(", "removeItem(at:"):
            with self.subTest(api=forbidden):
                self.assertNotIn(forbidden, source)
        raw = str(mod.PATCHES)
        self.assertIn("https://ani.jkcoxson.com", raw)
        self.assertIn("<PC> <Windows;6.2(0,0);9200>", raw)


if __name__ == "__main__":
    unittest.main()
