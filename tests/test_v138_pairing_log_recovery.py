"""V138: user-provided reset trace cannot invalidate a valid pairing record."""
import importlib.util
from pathlib import Path
import os
import unittest
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v138rp',BASE/'scripts/patch_v138_pairing_log_recovery.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class RPTraceTests(unittest.TestCase):
    def test_reset_is_transport_not_pairing(self):
        old='''            if msg.contains("invalidconf") || msg.contains("pairing") || msg.contains("handshake") ||
                msg.contains("connection reset") || msg.contains("connectionreset") {'''
        new=mod.gateway(old)
        self.assertNotIn('msg.contains("connection reset")',new)
        self.assertIn('msg.contains("pairing")',new)
        self.assertIn('SCARLET_V138_RP_ERROR_CLASSIFICATION',new)
        self.assertEqual(mod.gateway(new),new)
    def test_boot_not_mark_nil_device_as_success(self):
        old='''            let deviceUDID = try await fetchUDID()
            debugLog("[AppBootManager] startMinimuxer(): Minimuxer fetchUDID() based connection test SUCCEEDED. UDID: \\(deviceUDID ?? "nil")")
            self.needsPairingPrompt = false'''
        new=mod.boot(old)
        self.assertIn('guard let deviceUDID = try await fetchUDID(), !deviceUDID.isEmpty',new)
        self.assertNotIn('SUCCEEDED. UDID:',new)
        self.assertEqual(mod.boot(new),new)
    def test_only_explicit_static_fallback(self):
        old='''    let result = try? await withRemotePairingRetry {
        try await minimuxer.core.fetchUDID()
    }
    if let udid = result ?? nil, !udid.isEmpty, udid != "XXXXX-XXXX-XXXXX-XXXX" {
        return udid
    }
    if useStatic {
        return PairingFileManager.shared.pairingUDID
    }
    return nil'''
        new=mod.wrapper(old)
        self.assertIn('throw error',new)
        self.assertIn('if useStatic',new)
        self.assertIn('stage=udid result=verified via=transport',new)
        self.assertNotIn('try? await withRemotePairingRetry',new)
        self.assertEqual(mod.wrapper(new),new)
    def test_unknown_revision_fails_closed(self):
        for transform in (mod.gateway,mod.wrapper,mod.boot):
            with self.assertRaises(ValueError):transform('unsupported revision')
    def test_generated_sources_if_available(self):
        mux=os.getenv('V138_PATCHED_MINIMUXER')
        side=os.getenv('V138_PATCHED_SIDESTORE')
        if not mux or not side:return
        for path,fn in ((Path(mux)/mod.GATEWAY,mod.gateway),
                        (Path(side)/mod.WRAPPER,mod.wrapper),
                        (Path(side)/mod.BOOT,mod.boot)):
            text=path.read_text()
            self.assertEqual(fn(text),text)
            self.assertNotIn('SecItemDelete(',text)
if __name__=='__main__':unittest.main()
