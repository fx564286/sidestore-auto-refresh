"""Offline safety/compatibility contracts for isolated xtool Developer Services V6.

Verifies developer portal request alignment and token-expiry bucket diagnostics
without contacting Apple or logging credentials, token values, or 2FA.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("nrg_v6",ROOT/"scripts"/"xtool_nrg_auth_devportal_v6.py")
v6=importlib.util.module_from_spec(sp)
sp.loader.exec_module(v6)

class XtDevPortalV6Tests(unittest.TestCase):
    def test_idempotent_exact_source_and_fails_closed(self):
        for path,changes in v6.PATCHES.items():
            for upstream,revised in changes:
                with self.subTest(path=str(path)):
                    source="// upstream\n"+upstream
                    applied=v6.patch(source,changes,str(path))
                    self.assertEqual(applied,v6.patch(applied,changes,str(path)))
                    self.assertIn(v6.MARKER,applied)
                    with self.assertRaises(ValueError):
                        v6.patch("unexpected source",changes,str(path))

    def test_devportal_client_identity_matches_grandslam(self):
        change=v6.PATCHES[v6.DEV][0][1]
        self.assertIn("DeviceInfo.nrgSideStoreAuth",change)
        self.assertIn("DeviceInfo.nrgWindowsClientInfo",change)
        self.assertIn("DeviceInfo.clientInfoKey",change)
        self.assertIn("DeviceInfo.xcodeVersionKey",change)
        self.assertIn('"14.2 (14C18)"',change)
        self.assertIn('httpRequest.headerFields[.acceptLanguage] = "en-us"',change)

    def test_token_expiry_state_does_not_expose_token_or_account(self):
        change=v6.PATCHES[v6.LOGIN][0][1]
        self.assertIn("timeIntervalSinceNow",change)
        self.assertIn('"expired"',change)
        self.assertIn('"near_expiry"',change)
        self.assertIn('"valid"',change)
        self.assertIn("NRG_XTOOL_AUTH_TRACE",change)
        self.assertNotIn("print(token.value)",change)
        self.assertNotIn("print(loginData.adsid)",change)

    def test_teams_diagnostics_are_code_only_and_signing_free(self):
        change=v6.PATCHES[v6.AUTH][0][1]
        self.assertIn("DeveloperServicesListTeamsRequest()",change)
        self.assertIn("DeveloperServicesAPIVersionLegacy.Error",change)
        self.assertIn("phase=listTeams api_code=",change)
        source=(ROOT/"scripts"/"xtool_nrg_auth_devportal_v6.py").read_text()
        for forbidden in ("revokeCertificate(", "deleteAppID(", "resetProvisioning()", "removeItem(", "signInPlace(", "print(loginToken.token)"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,source)

if __name__=="__main__":
    unittest.main()
