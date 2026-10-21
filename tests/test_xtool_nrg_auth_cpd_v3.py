"""Offline contract tests for xtool 1.22.2 SideInstaller parity GrandSlam V3.

No credentials, login, network, device operations or certificate changes.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "nrg_xtool_auth_cpd_v3",
    ROOT / "scripts" / "xtool_nrg_auth_cpd_v3.py"
)
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)


class NRGXtoolAuthCPDV3Tests(unittest.TestCase):
    def test_each_patch_idempotent_and_requires_v1(self):
        for path, edits in v3.PATCHES.items():
            with self.subTest(path=path):
                for original, replacement in edits:
                    upstream = f"prefix {v3.V1}\n" + original + "\nsuffix"
                    result = v3.transform(upstream, original, replacement, str(path))
                    self.assertEqual(
                        result, v3.transform(result, original, replacement, str(path))
                    )
                    self.assertIn(v3.MARKER, result)
                    with self.assertRaises(ValueError):
                        v3.transform("upstream changed unexpectedly", original, replacement, str(path))

    def test_compat_cpd_matches_sideinstaller_minimal_string_shape(self):
        code = v3.PATCHES[v3.OPS][0][1]
        self.assertIn('clientData = [', code)
        for key, value in {
            "bootstrap": "true", "icscrec": "true",
            "pbe": "false", "prkgen": "true",
            "svct": "iCloud", "loc": "en_US"
        }.items():
            self.assertIn(f'"{key}": "{value}"', code)
        self.assertIn("AnisetteData.deviceIDKey", code)
        self.assertIn("AnisetteData.machineIDKey", code)
        self.assertIn("AnisetteData.oneTimePasswordKey", code)
        self.assertNotIn("DeviceInfo.nrgWindowsClientInfo", code)
        self.assertNotIn("deviceInfo.dictionary", code)

    def test_url_bag_and_gsa_share_windows_identity(self):
        lookup = v3.PATCHES[v3.LOOKUP][0][1]
        client = v3.PATCHES[v3.CLIENT][0][1]
        self.assertIn("DeviceInfo.nrgWindowsClientInfo", lookup)
        self.assertIn('request.headerFields[.init(DeviceInfo.deviceIDKey)!] = nil', lookup)
        self.assertIn('request.headerFields[.userAgent] = "akd/1.0 CFNetwork/808.1.4"', lookup)
        self.assertIn('httpRequest.headerFields[.accept] = "text/x-xml-plist"', client)
        self.assertIn('httpRequest.headerFields[.init("Connection")!] = "close"', client)

    def test_no_cert_or_account_mutations(self):
        text = (ROOT / "scripts" / "xtool_nrg_auth_cpd_v3.py").read_text()
        for forbidden in ("auth login", "revokeCertificate(", "deleteAppID(", "signInPlace(", "XTLAuthToken", "xtool auth logout"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
