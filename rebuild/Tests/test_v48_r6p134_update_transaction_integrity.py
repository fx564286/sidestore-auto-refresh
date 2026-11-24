"""R134: bind update bytes and existing identity before native provisioning."""
from pathlib import Path
import importlib.util
import unittest
ROOT=Path(__file__).resolve().parents[1]
W=(ROOT/'integration/ScarletDeviceInstallAgent.swift.txt').read_text()
H=(ROOT/'HostApp/ScarletSelfUpdateIntent.swift').read_text()
G=(ROOT/'integration/wire_scarlet_auth.py').read_text()

class UpdateIntegrity(unittest.TestCase):
    def test_digest_transport_and_private_snapshot_precedes_prepare(self):
        self.assertIn('selfUpdateSHA256: manifest.sha256',H)
        self.assertIn('parts.count != 2 && parts.count != 5',G)
        self.assertIn('payload[@"selfUpdateSHA256"] = parts[4]',G)
        self.assertIn('selfUpdateSHA256: String? = nil',G)
        self.assertIn('let digest = payload["selfUpdateSHA256"] as? String',W)
        self.assertIn('copySelfUpdateSnapshot(from: stagedURL, to: fileURL)',W)
        self.assertLess(W.index('try verifySelfUpdateDigest(fileURL, expected: digest)'),W.index('ScarletInstallTeamAuthority.prepare('))
        self.assertLess(W.index('try verifySelfUpdateDigest(fileURL, expected: digest)'),W.index('selfUpdateFence.set(SelfUpdateExpectation'))
        self.assertIn('privateSnapshotDirectory',W)
        self.assertIn('values.isSymbolicLink != true',W)
        self.assertIn('try output.write(contentsOf: block)',W)
        self.assertIn('total <= 150 * 1024 * 1024',W)
    def test_provisioning_does_not_create_alternate_ids(self):
        self.assertIn('static func validateSelfUpdateInput(',W)
        self.assertIn('static func selfUpdateProvisioningParentID(',W)
        self.assertIn('expected.extensionIDs == mapped',W)
        self.assertIn('targetAppBundle.bundleIdentifier == "com.kdt.livecontainer.P8EZT3U5N4"',W)
        self.assertIn('ScarletDeviceInstallAgent.validateSelfUpdateInput(targetAppBundle',G)
        self.assertIn('ScarletDeviceInstallAgent.selfUpdateProvisioningParentID(',G)
        self.assertIn('parentID = exactHostID',G)
        self.assertIn('selfUpdateProvisioningParentID',G.split('def patch_idempotent_team_provisioning',1)[1].split('def patch_sidestore',1)[0])
    def test_simulator_error_summary_excludes_objc_selector_and_warnings(self):
        spec=importlib.util.spec_from_file_location('smoke',ROOT/'diagnostics/scarlet_ios_simulator_smoke.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        lines=['18 | + (instancetype)extensionWithIdentifier:(NSString *)identifier error:(NSError **)error;',
               '/tmp/a.m:30:115: warning: undeclared selector error:',
               '/tmp/a.swift:9:5: error: actual compiler error',
               'ld: building for iOS Simulator, but linking in object file built for iOS',
               'clang: error: linker command failed with exit code 1']
        got=mod.extract_build_errors('\n'.join(lines))
        self.assertEqual(got,lines[2:])
    def test_simulator_ffi_sdk_isolation(self):
        link=(ROOT/'integration/link_scarlet_pairing.py').read_text()
        workflow=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
        self.assertIn('SCARLET_PAIRING_ARCHIVE[sdk=iphonesimulator*]',link)
        self.assertIn('SCARLET_PAIRING_ARCHIVE = ScarletPairingFFI.a',link)
        self.assertIn('$(PROJECT_DIR)/$(SCARLET_PAIRING_ARCHIVE)',link)
        self.assertIn('cargo build --release --locked --target aarch64-apple-ios-sim',workflow)
        self.assertIn('engine/LiveContainer/ScarletPairingFFISimulator.a',workflow)
        self.assertIn('test "$device_digest" =',workflow)
        self.assertLess(workflow.index('Build LiveContainer with integrated SideStoreSupport for real iOS'),
                        workflow.index('rustup target add aarch64-apple-ios-sim'))
if __name__=='__main__': unittest.main()
