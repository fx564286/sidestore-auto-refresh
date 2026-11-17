"""P94: owned manual SideStore P12 must reach the separate LC signer safely."""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HOST=(ROOT/'rebuild/HostApp/ScarletIntegratedHostView.swift').read_text()
PANEL=(ROOT/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
WORKFLOW=(ROOT/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
SIGNER_PATCH=ROOT/'rebuild/integration/scarlet_p94_zsign_der.py'
APPLY=(ROOT/'rebuild/integration/apply_scarlet_host.py').read_text()

class ExplicitOwnerCertificateGuestSigner(unittest.TestCase):
    def test_one_active_saved_apple_id_team_owner_is_reverified_after_import(self):
        body=PANEL.split('private func importExportedP12()',1)[1].split('    var body:',1)[0]
        self.assertIn('if result.0 {',body)
        self.assertIn('let readback = await ScarletNativeSavedAccounts.list()',body)
        self.assertIn('readback.accounts.filter({ $0.active }).count == 1',body)
        self.assertIn('$0.active && $0.id == active.id && $0.teamID == active.teamID',body)
        self.assertIn('account_p12_guest_signer_blocked',body)
        self.assertIn('active_owner_changed',body)
        self.assertIn('account_p12_guest_signer_trial_requested',body)
        self.assertIn('nativeCandidate: (archive: archive, password: password)',body)
        self.assertNotIn('SecItemDelete(',body)

    def test_existing_livecontainer_exact_rollback_and_kernel_check_guarded(self):
        self.assertIn('enum ScarletGuestSignerRecovery {',HOST)
        self.assertIn('prefs.set(original, forKey: backupCert)',HOST)
        self.assertIn('prefs.set(originalPassword, forKey: backupPassword)',HOST)
        self.assertIn('guard prefs.synchronize() else',HOST)
        self.assertIn('LCUtils.validateJITLessSetup { valid, _ in',HOST)
        self.assertIn('restoreOriginal(prefs)',HOST)
        self.assertGreaterEqual(HOST.count('guard profile == .matched else {'),2)
        self.assertIn('entitlements["get-task-allow"] as? Bool == true',HOST)
        self.assertIn('allowed.contains(candidateDER) ? .matched : .different',HOST)
        self.assertIn('LCUtils.scarletCertificateDER(',HOST)
        self.assertNotIn('SecPKCS12Import(archive as CFData',HOST)

    def test_openssl_export_contains_only_public_certificate_der(self):
        src=SIGNER_PATCH.read_text()
        for part in ('ZSignAsset signer;', 'signer.InitSimple(', 'i2d_X509(', 'OPENSSL_free(derBytes)',
                     'NSData *der', 'scarletCertificateDERWithCert:',
                     'scarletCertificateDERWithKeyData:', 'private_key_exported'):
            self.assertIn(part,src)
        self.assertNotIn('i2d_PrivateKey',src)
        self.assertNotIn('PEM_write_bio_PrivateKey',src)
        self.assertIn('attach_p94_zsign_public_der(engine)',APPLY)

    def test_injection_applies_to_exact_pinned_native_paths_without_changing_signer(self):
        spec=importlib.util.spec_from_file_location('p94_zsign_der',SIGNER_PATCH)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        parent=Path('/workspace/scarlet-p91-20261117/engine/LiveContainer')
        if not parent.is_dir():
            self.skipTest('pinned LC is unavailable in this runtime, source-level test only')
        paths=['ZSign/zsign.mm','ZSign/zsigner.h',
            'LiveContainerSwiftUI/Utilities/LCUtils.m',
            'LiveContainerSwiftUI/Utilities/LCUtils.h']
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for rel in paths:
                (root/rel).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(parent/rel,root/rel)
            verified=module.attach_p94_zsign_public_der(root)
            self.assertTrue(verified['certificate_der_only'])
            self.assertTrue(verified['original_zsign_parser'])
            self.assertFalse(verified['private_key_exported'])
            for rel in paths:self.assertIn('scarletCertificateDERWith', (root/rel).read_text())

    def test_independent_ios_version_and_public_unsigned_release_route(self):
        self.assertIn('fix/scarlet-v48-r6p94-explicit-p12-guest-signer-20261117',WORKFLOW)
        self.assertIn('--host-build-version 3.8.94',WORKFLOW)
        self.assertIn('version="3.8.94"',WORKFLOW)
        self.assertIn('tag=scarlet-v48-r6p94-p12-guest-signer-unsigned-20261117',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6P94-P12-GUEST-SIGNER-UNSIGNED.ipa',WORKFLOW)
        self.assertIn('"CFBundleIdentifier"]=="com.kdt.livecontainer.P8EZT3U5N4"',WORKFLOW)

if __name__=='__main__': unittest.main()
