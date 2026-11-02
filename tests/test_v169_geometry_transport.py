"""V169 regression: one physical viewport authority and authenticated RP fallback."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "v169", ROOT / "scripts/patch_v169_event_geometry_transport.py")
v169 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v169)

class V169Regressions(unittest.TestCase):
    def test_geometry_uses_one_window_safe_area_and_lifecycle_events(self):
        source = """// SCARLET_V136_ROTATION_ATOMIC
// SCARLET_V141_INSET_AWARE_SETTLE
// SCARLET_V151_UNIFIED_GUEST_GEOMETRY
@property(nonatomic) UIInterfaceOrientation nrgV55LastHostOrientation;
portraitTop = MAX(physicalInsets.top, self.view.superview.safeAreaInsets.top);
portraitBottom = MAX(physicalInsets.bottom, self.view.superview.safeAreaInsets.bottom);
- (void)nrgV55ReconcileRotationGeometry {"""
        generated = v169.decorated(source)
        self.assertIn('portraitTop = physicalInsets.top;', generated)
        self.assertNotIn('MAX(physicalInsets.top, self.view.superview.safeAreaInsets.top)', generated)
        self.assertIn('viewDidLayoutSubviews', generated)
        self.assertIn('viewSafeAreaInsetsDidChange', generated)
        self.assertIn('nrgV136GeometryStable:window', generated)
        self.assertIn('CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport)', generated)
        self.assertEqual(v169.decorated(generated), generated)

    def test_all_four_delayed_reflows_removed(self):
        source = '''// SCARLET_V141_ROTATION_SAFEAREA_SETTLE
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.10) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
            // SCARLET_V141_ROTATION_SAFEAREA_SETTLE: iOS 27 often settles
            // top safe-area AFTER UIWindow width/height have stabilized.
            // Two final bounded checks, never a repeating timer.
            for delay in [0.55, 0.95] {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak windowScene] in
                    guard let windowScene, windowScene.activationState == .foregroundActive else { return }
                    MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
                }
            }'''
        generated = v169.delegate(source)
        self.assertNotIn('asyncAfter', generated)
        self.assertEqual(v169.delegate(generated), generated)

    def test_nil_vpn_peer_requires_authenticated_remote_pairing(self):
        source = '''// SCARLET_V164_TRANSPORT_RESYNC
        guard let initialHost = gateway.deviceEndpointIp, !initialHost.isEmpty else {
            throw firstError
        }
        let initialPort = gateway.getPort(for: .rppairing)'''
        generated = v169.pairing(source)
        for required in ['resolveV140RemotePairingEndpoint()',
                         'let verified = try await operation()',
                         'gateway.setDeviceEndpointIp(nil)',
                         'record=preserved', 'discovery=absent']:
            self.assertIn(required, generated)
        self.assertEqual(v169.pairing(generated), generated)

    def test_dualstack_utun_keeps_ipv4_pairing_candidate(self):
        before = '''                 $0.tunnelType == .utun && 
                !$0.interfaceAddresses.v4.isEmpty && $0.interfaceAddresses.v6.isEmpty 
        guard !candidates.isEmpty else { return (nil, nil, false) }
        return (nil, nil, false)
    }

    private func isValidCandidatePeer
                debugLog("[minimuxer] [iface] using the first uTun vpn interface info")'''
        after = v169.tunnel(before)
        self.assertIn('SCARLET_V169_DUALSTACK_TUNNEL_DISCOVERY', after)
        self.assertIn('!$0.interfaceAddresses.v4.isEmpty', after)
        self.assertNotIn('$0.interfaceAddresses.v6.isEmpty', after)
        self.assertIn('no_reachable_ipv4_peer', after)
        self.assertIn('no_ipv4_peer_candidate', after)
        self.assertEqual(v169.tunnel(after), after)

    def test_no_mutation_of_private_credentials_or_user_data(self):
        source = (ROOT / 'scripts/patch_v169_event_geometry_transport.py').read_text()
        for forbidden in ('SecItemDelete(', 'removePairingFile(', 'clearAllData(',
                          'uninstallApp(', 'removeGuest(', 'deleteCertificate('):
            self.assertNotIn(forbidden, source)

if __name__ == '__main__':
    unittest.main()
