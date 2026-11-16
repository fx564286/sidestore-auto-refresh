"""P81: exact upstream repair + independent contract gates, not status-bar masking."""
from pathlib import Path
import sys
import unittest
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'diagnostics'))
from verify_p81_native_integration import (OLD,NEW,MARK,verify_original_archive,
                                           verify_swift_importer)
G=(R/'integration/apply_scarlet_host.py').read_text()
H=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
I=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P81NativeArchiveRegression(unittest.TestCase):
    def test_original_archive_success_and_error_distinguished(self):
        native=G.split('def add_r6p79_mapped_archive_fallback(',1)[1].split('def hide_embedded_sidestore_guest_navigation(',1)[0]
        for token in ('source.count(original_completion) == 1',
                      'source.replace(original_completion, checked_completion, 1)',
                      'scarletArchiveReadResult == ARCHIVE_EOF',
                      'scarletArchiveWriteCloseResult >= ARCHIVE_WARN',
                      'try FileManager.default.removeItem(at: partialPayload)',
                      'scratch.path == pending.path'):
            self.assertIn(token,native)
        self.assertNotIn('removeItem(at: outputFolder)',native)
        self.assertNotIn('SecItemDelete',native)
    def test_replayed_reference_contract_detects_any_unrelated_archive_rewrite(self):
        reference='prefix\n'+OLD+'\n'
        patched='prefix\n'+NEW+'\n\n'+MARK+'\nreturn (ok && wrote) ? 0 : 1;\narchive_entry_filetype(entry)==AE_IFLNK\nhasAppPlist && entries<=80000\n// R6P79_MAPPED_IPA_FALLBACK_END'
        self.assertTrue(verify_original_archive(reference,patched)['exact_original_method_except_failure_return'])
        with self.assertRaises(AssertionError):
            verify_original_archive(reference,patched.replace('prefix','mutated unrelated code'))
        with self.assertRaises(AssertionError):
            verify_original_archive(reference,patched.replace('ARCHIVE_EOF &&','ARCHIVE_OK &&'))
    def test_original_native_import_pipeline_reused_and_plist_required(self):
        candidate='\n'.join([
            'func installIpaFile(_ url:URL) async throws {',
            'let result = extract(path, destination, progress)',
            'guard result != 0 else { return result }',
            'scratch.path == pending.path',
            'let partialPayload = scratch.appendingPathComponent("Payload"',
            'try FileManager.default.removeItem(at: partialPayload)',
            'let originalAppComplete = before.contains(where: { name in',
            'let recoveredAppComplete = after.contains(where: { name in',
            'appendingPathComponent("Info.plist")',
            'throw NSError(domain: "ScarletGuestArchive", code: 80',
            'let fallback = scarletExtractGuestIPAFromMappedData(',
            'let payloadContents = try fm.contentsOfDirectory(atPath: payloadPath.path)',
            'patchExecAndSignIfNeed(completionHandler:',
            'scarletTransactionalReplace',
        ])
        verify_swift_importer(candidate)
        with self.assertRaises(AssertionError):
            verify_swift_importer(candidate.replace('scratch.path == pending.path','false'))
    def test_other_working_runtime_owners_must_not_be_changed_for_zip_fix(self):
        self.assertIn('nativeStatusBarCollisionShield = false',H)
        self.assertIn('settings_account_switch_verified',G)
        self.assertIn('ScarletNativeSavedAccounts.activate(id)',G)
        self.assertIn('guestImportWorkerFinished()',I)
        self.assertNotIn('removeCertificate()',I)
        self.assertIn('verify_p81_native_integration.py',W)
    def test_expected_ios_archiving_and_distinct_version(self):
        for token in ('fix/scarlet-v48-r6p81-upstream-import-validation-20261116',
                      '--host-build-version 3.8.81',
                      'r6p81',
                      'Scarlet-Crystal-V48-R6P81-IMPORT-VALIDATED-UNSIGNED.ipa'):
            self.assertIn(token,W)
if __name__=='__main__':unittest.main()
