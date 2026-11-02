"""V175 RP preflight: own advertised port first; restore unverified port."""
from pathlib import Path
import importlib.util
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v175", ROOT/"scripts/patch_v175_stikdebug_port_preflight.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
FIXTURE = """// SCARLET_V172_OWN_DEVICE_RP_ADVERT
private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
    do {
        return try await operation()
    } catch {
        throw error
    }
}
"""
class V175PortParity(unittest.TestCase):
    def test_discovered_port_precedes_original_first_operation(self):
        src = mod.patch(FIXTURE)
        self.assertEqual(mod.patch(src), src)
        self.assertEqual(src.count(mod.MARKER), 1)
        self.assertLess(src.index("v175Gateway.setPort(v175Advert.port"),
                        src.index("let verified = try await operation()"))
        self.assertLess(src.index("let verified = try await operation()"),
                        src.index("    do {\n        return try await operation()"))

    def test_failed_candidate_rolls_back_but_identity_failure_stops(self):
        src = mod.patch(FIXTURE)
        self.assertIn("v175Gateway.getPort(for: .rppairing) == v175Advert.port", src)
        self.assertIn("v175Gateway.setPort(v175OriginalPort, for: .rppairing)", src)
        self.assertIn("remotePairingPortCache = v175OriginalPort", src)
        self.assertIn('message.contains("pairverifyfailed")', src)
        self.assertIn("throw error", src)

    def test_only_binds_after_own_phone_advert_verified(self):
        with self.assertRaises(ValueError):
            mod.patch(FIXTURE.replace("SCARLET_V172_OWN_DEVICE_RP_ADVERT", "UNTRUSTED"))
        self.assertIn("resolveV140RemotePairingEndpoint()", mod.NEW_ENTRY)
        self.assertIn("v175Gateway.deviceEndpointIp == v175Host", mod.NEW_ENTRY)

    def test_no_saved_pairing_or_cert_modification(self):
        source = (ROOT/"scripts/patch_v175_stikdebug_port_preflight.py").read_text()
        for forbidden in ("deletePairingFile(", "savePairingFile(", "SecItemDelete(",
                          "refreshCertificate(", "removeApp(", "setPairingFileData("):
            self.assertNotIn(forbidden, source)

if __name__ == "__main__":
    unittest.main()
