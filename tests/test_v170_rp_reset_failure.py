"""V170 pairing transport reset must never be interpreted as invalid pairing."""
from pathlib import Path
import importlib.util
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "patch_v170_rp_reset_failure", BASE/"scripts/patch_v170_rp_reset_failure.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PairingResetContract(unittest.TestCase):
    def test_patch_preserves_existing_retries_and_does_not_mutate_records(self):
        minimal = '''// SCARLET_V164_TRANSPORT_RESYNC
// SCARLET_V169_NO_VPN_PEER_FALLBACK
private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
        remotePairingPortCache = initialPort
        throw lastError
    }
}

public var minimuxerStatusPublisher: Any { fatalError() }
'''
        result = mod.patch(minimal)
        self.assertEqual(result, mod.patch(result))
        self.assertIn("remotePairingHandshakeReset", result)
        self.assertIn('transientReset &&', result)
        self.assertIn('terminalTransport.contains("connectionreset")', result)
        self.assertIn('record=preserved', result)
        self.assertNotIn("deletePairingFile", result)
        self.assertNotIn("savePairingFile", result)
        self.assertNotIn("pairingFile = ", result)
        self.assertIn("throw lastError", result)

    def test_failure_contract_preserved_without_secrets(self):
        f = (BASE / "scripts/templates/combined_failure.swift").read_text(encoding="utf-8")
        self.assertIn("case remotePairingHandshakeReset", f)
        self.assertIn("case .remotePairingHandshakeReset:", f)
        self.assertIn("Do not erase saved pairing or signing data.", f)
        self.assertIn('LCStructuredFailureCauseV1', (BASE/"scripts/patch_v170_rp_reset_failure.py").read_text())
        self.assertIn('safeCause?.rawValue', f)

if __name__=="__main__":
    unittest.main()
