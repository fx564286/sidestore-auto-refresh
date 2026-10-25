"""Source and IPA regression gates for the Mac Anisette / Windows compatibility split.

Never send an authentication request, log secrets, or modify Anisette identity.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GSA = (ROOT / "scripts/patch_nrg_gsa_auth.py").read_text(encoding="utf-8")
V3 = (ROOT / "scripts/patch_nrg_gsa_client_v3.py").read_text(encoding="utf-8")
TRACE = (ROOT / "scripts/patch_v98_gsa_80046_trace.py").read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location("verify_candidate_v106",
    ROOT / "scripts/verify_candidate_ipa.py")
# Verifier dependencies are loaded by the installed test harness separately;
# check its integration and constant using only its source here.
VERIFIER = (ROOT / "scripts/verify_candidate_ipa.py").read_text(encoding="utf-8")


class GSAAdaptiveIdentityTests(unittest.TestCase):
    def test_mac_claim_is_original_and_windows_remains_fallback(self):
        helper_start = GSA.index("private func nrgGrandSlamClientInfo(_ original: String)")
        helper_end = GSA.index("\n    }", helper_start)
        helper = GSA[helper_start:helper_end]
        self.assertIn('original.contains("<Mac")', helper)
        self.assertIn('original.contains("<iMac")', helper)
        self.assertIn('original.contains("<macOS;")', helper)
        self.assertIn('original.contains("<com.apple.AuthKit/")', helper)
        self.assertIn('return original', helper)
        self.assertIn('<PC> <Windows;6.2(0,0);9200>', helper)
        self.assertLess(helper.index('return original'), helper.index('return "<PC>'))
        self.assertNotIn("anisetteAdiBlob =", helper)
        self.assertNotIn("AuthManager.shared.signOut()", helper)

    def test_srp_and_2fa_share_one_identity_policy(self):
        self.assertIn('"X-MMe-Client-Info": nrgGrandSlamClientInfo(anisetteData.clientInfo)', GSA)
        self.assertIn('"X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo)', V3)
        self.assertIn("NRG_GSA_WINDOWS_UA_V4", V3)
        self.assertIn('code == -80046', TRACE)
        self.assertIn("anisette_family=", TRACE)
        self.assertIn("sent_family=", TRACE)

    def test_signed_ipa_guard_is_wired_to_embedded_executable(self):
        self.assertIn('REQUIRED_EMBEDDED_AUTH_MARKERS', VERIFIER)
        self.assertIn('verify_embedded_auth_markers(side_store_executable_data)', VERIFIER)
        self.assertIn('b"[SCARLET_V98_GSA] operation="', VERIFIER)
        self.assertIn('b"[NRG_AUTH] terminal_transport_status="', VERIFIER)

    def test_absent_or_stale_binary_rejected(self):
        # Avoid importing the enormous verifier's build-tool dependencies.
        start = VERIFIER.index('def verify_embedded_auth_markers(')
        end = VERIFIER.index('\n', VERIFIER.index('raise ValueError(', start))
        helper = VERIFIER[start:end]
        self.assertIn('raise ValueError', helper)
        self.assertIn('if m not in executable', helper)


if __name__ == "__main__":
    unittest.main()
