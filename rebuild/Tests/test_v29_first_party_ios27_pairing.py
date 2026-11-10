"""Scarlet V29 genuine iOS27 on-device pairing integration contracts.

The pairing is performed by an audited native Rust host from pinned StikPair,
not by opening SideInstaller or importing a fabricated plist. On success
SideStore's actual Minimuxer verifies the candidate before any saved
pairing record is changed. This makes no promise of iOS self-renewal.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"HostApp/ScarletNativeDevicePairing.swift").read_text()
PANEL=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
XPC=(ROOT/"HostApp/ScarletAuthXPCSupport.swift").read_text()
WIRE=(ROOT/"integration/wire_scarlet_auth.py").read_text()
WORKER=(ROOT/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
BUILD=(ROOT/"integration/apply_scarlet_host.py").read_text()
LINK=(ROOT/"integration/link_scarlet_pairing.py").read_text()
CI=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
GLASS=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()

class V29NativePairing(unittest.TestCase):
    def test_real_rust_rppairing_engine_linked_not_stubbed(self):
        self.assertIn("7c911d8319dc5bcc411bf299d963689e26009b0b",LINK)
        self.assertIn("libstikpair_ffi.a",LINK)
        self.assertIn('stikpair_run_host(',UI)
        self.assertIn('StikPairResult()',UI)
        self.assertIn('stikpair_result_free(&result)',UI)
        self.assertIn('scarletPairingReady',UI)
        self.assertIn('scarletPairingPIN',UI)
        self.assertIn('git clone --filter=blob:none https://github.com/StikDebug/StikPair.git',CI)
        self.assertIn('rustup target add aarch64-apple-ios',CI)
        self.assertIn('cargo build --release --locked --target aarch64-apple-ios',CI)
        self.assertIn('link_scarlet_pairing.py',CI)
        self.assertIn('licenseFile.read_text()',LINK)
        self.assertIn('ScarletPairingThirdParty-LICENSE.txt',LINK)

    def test_native_ios27_settings_workflow_and_phone_notification(self):
        self.assertIn('@available(iOS 27.0, *)',UI)
        self.assertIn('BGContinuedProcessingTaskRequest(',UI)
        self.assertIn('BGTaskScheduler.shared.register(',UI)
        self.assertIn('NetService(domain: ""',UI)
        self.assertIn('_remotepairing-pairable-host._tcp.',UI)
        self.assertIn('UNUserNotificationCenter.current().add(',UI)
        self.assertIn('Task { @MainActor in model.showPIN(pin) }',UI)
        self.assertIn('ScarletNativePairingInstaller.install(',UI)
        self.assertIn('ScarletDevicePairingSheet()',PANEL)
        self.assertIn('SCARLET_NATIVE_DEVICE_PAIRING',PANEL)
        self.assertIn('SCARLET_NATIVE_RPPAIR_START',UI)
        self.assertNotIn('PairingLiveActivity',UI)
        self.assertNotIn('SideInstaller.app',UI)
        self.assertIn('NSLocalNetworkUsageDescription',BUILD)
        self.assertIn('NSBonjourServices',BUILD)
        self.assertIn('ScarletDevicePairingModel.shared.registerAtLaunch()',BUILD)

    def test_private_pairing_record_validated_and_committed_only_after_probe(self):
        self.assertIn('pairingManager.parse(',WORKER)
        self.assertIn('try await AppBootManager.shared.startMinimuxer(',WORKER)
        self.assertIn('try await ensureMinimuxerReady()',WORKER)
        self.assertIn('pairingManager.savePairingFile(',WORKER)
        self.assertLess(
            WORKER.index('try await ensureMinimuxerReady()',WORKER.index('importDevicePairing')),
            WORKER.index('pairingManager.savePairingFile(',WORKER.index('importDevicePairing'))
        )
        self.assertIn('pairingManager.persistedActiveProtocol = .rppairing',WORKER)
        self.assertIn('pairingManager.fetchPairingFile()',WORKER)
        self.assertIn('previous != candidate',WORKER)
        self.assertNotIn('UserDefaults.standard.isPairingReset = true',WORKER)
        self.assertIn('record.length > 1048576',WIRE)
        self.assertIn('scarletInstallPairingRecord',WIRE)
        self.assertIn('client.scarletInstallPairingRecord(candidate)',XPC)
        self.assertIn('pairing_saved_and_transport_ready',XPC)

    def test_existing_four_apple_bundle_ids_and_native_liquid_glass_preserved(self):
        self.assertIn('noExtraBundleIdentifiers',LINK)
        self.assertIn('glassPlate(radius: isOpen ? 28 : 31)',GLASS)
        self.assertNotIn('SideStore guest',UI)
        self.assertNotIn('NSLog(',UI)
        self.assertNotIn('remoteServerURL',UI)
        self.assertNotIn('deleteApp(',WORKER)
        self.assertNotIn('revokeCertificate(',WORKER)

if __name__=="__main__":unittest.main()
