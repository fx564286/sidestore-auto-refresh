"""V31 regression: genuine SideStore pairing persistence, stable sheet,
and Scarlet's violet-native settings. No device/signing success is inferred.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKER=(ROOT/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
XPC=(ROOT/"integration/wire_scarlet_auth.py").read_text()
HOSTX=(ROOT/"HostApp/ScarletAuthXPCSupport.swift").read_text()
PAIR=(ROOT/"HostApp/ScarletNativeDevicePairing.swift").read_text()
PANEL=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
GLASS=(ROOT/"HostApp/ScarletNativeGlass.swift").read_text()
INTEGRATE=(ROOT/"integration/apply_scarlet_host.py").read_text()
CI=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()

class V31RealState(unittest.TestCase):
    def test_saved_state_comes_from_real_sidestore_record_and_minimuxer(self):
        read = WORKER[WORKER.index('static func inspectDevicePairing('):
            WORKER.index('// V29: in-app iOS 27 RPPairing')]
        self.assertIn('PairingFileManager.shared', read)
        self.assertIn('fetchPairingFile()', read)
        self.assertIn('pairing.parse(content: saved, preferred: .rppairing)', read)
        self.assertIn('ScarletGuestDeviceTransport.ensureReady()', read)
        self.assertIn('reply(true, "pairing_saved_and_transport_ready")', read)
        self.assertIn('reply(false, "pairing_saved_transport_unavailable")', read)
        self.assertNotIn('UserDefaults.standard.bool(', read)
        self.assertNotIn('print(saved)', read)

    def test_no_secrets_leave_worker_and_xpc_status_contract_is_typed(self):
        self.assertIn('scarletInspectDevicePairing:(void (^)(BOOL ready, NSString *status))reply;', XPC)
        self.assertIn('@selector(inspectDevicePairing:)', XPC)
        self.assertIn('client.scarletInspectDevicePairing', HOSTX)
        self.assertIn('pairing_state_read_timeout', HOSTX)
        self.assertIn('pairing_file_missing', HOSTX)
        self.assertIn('pairing_saved_transport_unavailable', HOSTX)
        self.assertNotIn('scarletInspectDevicePairing:(NSData*)', XPC)

    def test_post_restart_state_is_real_readback_and_generation_guarded(self):
        self.assertIn('func refreshStoredState()', PAIR)
        self.assertIn('generation == stateReadGeneration', PAIR)
        self.assertIn('guard !active && !stateReadInFlight', PAIR)
        self.assertIn('defer { stateReadInFlight = false }', PAIR)
        self.assertIn('stateReadGeneration &+= 1 // stale readbacks', PAIR)
        self.assertIn('verified = ready',PAIR)
        self.assertIn('savedRecordState = ready ? "페어링 됨"',PAIR)
        self.assertIn('pairing_restored',PAIR)
        self.assertIn('ScarletDevicePairingModel.shared.refreshStoredState()',HOST)
        self.assertIn('SCARLET_PERSISTED_PAIRING_STATUS', PAIR)

    def test_pairing_sheet_is_one_stable_host_owned_modal(self):
        self.assertNotIn('.sheet(isPresented: $isShowingInAppPairing)',PANEL)
        self.assertIn('Notification.Name("ScarletPresentDevicePairing")', PANEL)
        self.assertIn('Notification.Name("ScarletPresentDevicePairing")', HOST)
        self.assertIn('.sheet(isPresented: $showInAppDevicePairing)',HOST)
        self.assertEqual(HOST.count('ScarletDevicePairingSheet()'),1)
        self.assertIn('.presentationDetents([.large])',HOST)
        self.assertIn('SCARLET_STABLE_DEVICE_PAIRING_SHEET',HOST)

    def test_original_form_scrolling_and_purple_background_coexist(self):
        self.assertIn('func scarletSettingsPurplePalette() -> some View', GLASS)
        self.assertIn('.scarletNativeListTheme()', INTEGRATE)
        self.assertIn('.scarletSettingsPurplePalette()', INTEGRATE)
        self.assertIn('.scarletSettingsScrollLimit()', INTEGRATE)
        self.assertIn('0.104, green: 0.079, blue: 0.147',GLASS)
        self.assertIn('170.0/255, green: 150.0/255, blue: 1.0', GLASS)
        self.assertIn('LCSettingsView()', HOST)
        self.assertIn('.tabBarMinimizeBehavior(.onScrollDown)',
                      (ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text())

    def test_four_existing_bundle_ids_unchanged(self):
        self.assertIn('fix/scarlet-v31-pairing-persistence-sheet-purple-20261110', CI)
        self.assertNotIn('SideInstaller.app', PAIR)
        self.assertNotIn('newApplicationIdentifier',WORKER)

if __name__=='__main__':
    unittest.main()
