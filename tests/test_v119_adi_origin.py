"""V119 source-level provenance diagnostics regression; no Apple network access."""
import importlib.util
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v119', ROOT/'scripts/patch_v119_adi_origin.py')
v119=importlib.util.module_from_spec(spec);spec.loader.exec_module(v119)
FIX='''import Foundation
enum AnisetteProvider {
    static func fetch(handler: AnisetteServerHandler? = nil) async throws -> ALTAnisetteData {
        if UserDefaults.standard.useOnDeviceAnisette { return try await OnDeviceAnisetteManager.shared.fetchAnisetteData() }
        return try await fetchRemote(handler: handler)
    }
    static func fetchRemote(handler: AnisetteServerHandler? = nil) async throws -> ALTAnisetteData {
        let (anisetteData, newAdiBlob) = try await provider.fetchAnisetteDataWithFailover()
        if let freshBlob = newAdiBlob {
            AnisetteConfigManager.shared.anisetteAdiBlob = freshBlob.base64EncodedString()
        }

        return anisetteData
    }
}
'''
class Tests(unittest.TestCase):
    def test_patch_idempotent_and_two_markers(self):
        result=v119.transform(FIX)
        self.assertEqual(v119.transform(result),result)
        self.assertEqual(result.count(v119.MARK),2)
        self.assertIn('SCARLET_V119_ADI_RESULT',result)
        self.assertIn('server_catalog_hint=',result)
        self.assertIn('routing_override=',result)
    def test_fail_closed_on_unexpected_pinned_layout(self):
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            v119.transform(FIX.replace('return anisetteData','return somethingElse'))
        with self.assertRaisesRegex(ValueError,'partial'):
            v119.transform(v119.transform(FIX).replace('reused_prior_adi=','wrong='))
    def test_no_account_or_adi_mutation_added(self):
        added=v119.ROUTE+v119.REMOTE_NEW.replace(v119.REMOTE,'')
        for unsafe in ('SecItemDelete(', 'resetAnisette', 'signOut(', 'password=',
                       'newAdiBlob =', 'adiPb =', 'deleteConfigFile('):
            self.assertNotIn(unsafe, added)
        self.assertNotIn('serverURL.absoluteString',added)
    def test_label_is_explicitly_unverified_hint(self):
        self.assertIn('Catalog names are only hints',v119.ROUTE)
        self.assertIn('not proof',v119.REMOTE_NEW)
if __name__=='__main__':unittest.main()
