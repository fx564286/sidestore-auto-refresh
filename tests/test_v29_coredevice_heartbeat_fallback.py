"""Regression tests for real CoreDevice JIT transport without a mandatory heartbeat."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/patch_coredevice_idevice.py"

class V29CoreDeviceHeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text()

    def test_heartbeat_failure_does_not_abort_before_real_coredevice(self):
        s = self.source
        a = s.index("let heartbeat_client = match tokio::time::timeout(")
        b = s.index('transport_log("[SIDESTORE_COREDEVICE] TUNNEL_COREDEVICE_CONNECT_START");', a)
        heartbeat = s[a:b]
        self.assertIn('std::time::Duration::from_secs(5)', heartbeat)
        self.assertIn('HEARTBEAT_CONNECT_FAIL stage=heartbeat fallback=coredevice', heartbeat)
        self.assertIn('HEARTBEAT_CONNECT_TIMEOUT stage=heartbeat fallback=coredevice', heartbeat)
        self.assertIn('Ok(Err(_error)) => {', heartbeat)
        self.assertIn('Err(_) => {', heartbeat)
        self.assertIn('None', heartbeat)
        self.assertNotIn('return Err(', heartbeat)
        self.assertLess(heartbeat.index('if let Some(mut heartbeat)'), heartbeat.index('} else {'))
        self.assertIn('HEARTBEAT_IS_ACTIVE.store(false, Ordering::SeqCst)', heartbeat)

    def test_fallback_still_requires_real_authenticated_tunnel(self):
        s = self.source
        self.assertIn('CoreDeviceProxy::connect(provider_ref)', s)
        self.assertIn('RsdHandshake::new(rsd_stream)', s)
        self.assertIn('TUNNEL_RSD_HANDSHAKE_PASS', s)
        self.assertIn('RSD connect timed out after 12 seconds', s)
        self.assertIn('RSD handshake timed out after 15 seconds', s)
        self.assertIn('V29_JIT_HEARTBEAT_OPTIONAL', s)
        self.assertNotIn('rppairing_connect_quic_tunnel', s.split('new = r',1)[-1].split('free_path =',1)[0])

    def test_transport_teardown_still_clears_heartbeat(self):
        s = self.source
        self.assertIn('tunnel_heartbeat_stop()', s)
        self.assertIn('handle.abort()', s)
        self.assertIn('ACTIVE_HEARTBEAT.lock().unwrap()', s)

if __name__ == '__main__':
    unittest.main()
