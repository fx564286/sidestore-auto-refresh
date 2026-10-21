"""Offline safety and contract tests for hsc 434 / -22421 one-shot resync.

No requests to Apple, SideInstaller servers, devices, or developer account.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sp = importlib.util.spec_from_file_location("nrg_xtool_auth_resync_v4",ROOT/"scripts"/"xtool_nrg_auth_resync_v4.py")
v4 = importlib.util.module_from_spec(sp)
sp.loader.exec_module(v4)


class NRGXtoolAnisetteResyncTests(unittest.TestCase):
    def test_all_edits_idempotent_and_fail_closed(self):
        for path, replacements in v4.PATCHES.items():
            with self.subTest(file=path):
                for old, new in replacements:
                    self.assertNotEqual(old,new)
                    text=old
                    updated=v4.transform(text,[(old,new)],str(path))
                    self.assertEqual(updated,v4.transform(updated,[(old,new)],str(path)))
                    with self.assertRaises(ValueError):
                        v4.transform("unsupported source",[(old,new)],str(path))

    def test_only_init_one_retry_and_specific_apple_challenge(self):
        client='\n'.join(new for _old,new in v4.PATCHES[v4.CLIENT])
        self.assertIn("request is GrandSlamAuthInitRequest",client)
        self.assertIn("error.code == -22421",client)
        self.assertIn("error.hsc == 434",client)
        self.assertIn("let sim = error.resyncData",client)
        self.assertIn("sim.count <= 65536",client)
        self.assertIn("adi.nrgResync(sim: sim)",client)
        self.assertEqual(client.count("withEphemeralClient"),1)
        self.assertNotIn("GrandSlamAuthCompleteRequest",client)
        self.assertNotIn("GrandSlamValidateRequest",client)
        self.assertNotIn("GrandSlamAppTokensRequest",client)

    def test_sim_is_never_logged_and_can_be_plist_data_or_string(self):
        status=v4.PATCHES[v4.OPS]
        self.assertIn('case resyncData = "X-Apple-I-MD-DATA"',status[1][1])
        self.assertIn('c.decode(Data.self',status[1][1])
        self.assertIn('c.decode(String.self',status[1][1])
        self.assertIn('Data(base64Encoded: encoded)',status[1][1])
        for file,edits in v4.PATCHES.items():
            for old,new in edits:
                self.assertNotIn('print(sim)',new)
                self.assertNotIn('print(resyncData)',new)
                self.assertNotIn('print(body)',new)

    def test_remote_v3_payload_matches_sideinstaller(self):
        provider=v4.PATCHES[v4.OMNI][1][1]
        self.assertIn('url.appendingPathComponent("v3/get_headers")',provider)
        for field in ["identifier", "adiPb", "sim", "deviceId", "mdLu"]:
            self.assertIn(f"let {field}:",provider)
        self.assertIn('SHA256.hash(data: rawID)',provider)
        self.assertIn('sim.base64EncodedString()',provider)
        self.assertIn('userID.uuidString.lowercased()',provider)

    def test_no_storage_deletion_or_certificate_revocation(self):
        source=(ROOT/"scripts"/"xtool_nrg_auth_resync_v4.py").read_text()
        for action in (
            "resetProvisioning()", "AuthToken.clear()", "removeItem(",
            "revokeCertificate(", "deleteAppID(", "signInPlace(", "uninstall("
        ):
            with self.subTest(api=action):
                self.assertNotIn(action,source)


if __name__ == "__main__":
    unittest.main()
