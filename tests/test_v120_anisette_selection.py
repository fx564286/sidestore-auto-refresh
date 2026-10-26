"""V120 source-level selection regression; offline tests, no credentials used."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v120",ROOT/"scripts/patch_v120_anisette_selection.py")
v120=importlib.util.module_from_spec(spec);spec.loader.exec_module(v120)
FIX='''import Foundation
enum AnisetteProvider {
    static func fetchRemote() async throws -> ALTAnisetteData {
'''+v120.OLD_HEAD+'''        let provider = SideSign.AnisetteDataManager.shared
        let (anisetteData, newAdiBlob) = try await provider.fetchAnisetteDataWithFailover(
'''+v120.OLD_CALL+'''            identifier: identifier,
'''+v120.OLD_SUCCESS+'''        )
        return anisetteData
    }
}
'''
class TestV120(unittest.TestCase):
    def test_pinned_patch_idempotent(self):
        result=v120.transform(FIX)
        self.assertEqual(v120.transform(result),result)
        self.assertEqual(result.count(v120.MARK),2)
        self.assertIn('v120Custom.isEmpty ? v120Menu : v120Custom',result)
        self.assertIn('[preferred] + v120Catalog.filter',result)
        self.assertIn('servers: UserDefaults.standard.disableAnisetteRotation ? [servers[0]] : servers',result)
    def test_source_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            v120.transform(FIX.replace('startIndex: startIndex','startIndex: 1'))
        with self.assertRaisesRegex(ValueError,'incomplete'):
            v120.transform(v120.transform(FIX).replace('matches_selected=','not_matched='))
    def test_sensitive_account_state_is_unchanged(self):
        new=v120.NEW_HEAD+v120.NEW_SUCCESS
        for banned in ('SecItemDelete(','.signOut(','.adiPb = nil','removeObject(forKey: "adiPb")','password=','oneTimePassword='):
            self.assertNotIn(banned,new)
        self.assertNotIn('print(v120Requested)',new)
    def test_backend_marks_one_selected_server(self):
        s=(ROOT/'scripts/templates/v3_headless_runtime.swift').read_text(encoding='utf-8')
        segment=s[s.index('    static func anisetteList()'):s.index('    static func sidesignJSON()',s.index('    static func anisetteList()'))]
        self.assertIn('"active": selected == $0.address',segment)
        self.assertNotIn('active.contains($0.address)',segment)
        self.assertIn('UserDefaults.standard.removeObject(forKey: "textInputAnisetteURL")',s)
    def test_ui_shows_precedence_and_reloads(self):
        s=(ROOT/'scripts/templates/v3_unified_shell.swift').read_text(encoding='utf-8')
        view=s[s.index('struct V3AnisetteView:'):s.index('struct V3SideSignView:',s.index('struct V3AnisetteView:'))]
        self.assertIn('await store.setStringAndWait("menuAnisetteURL", server.address)',view)
        self.assertIn('await store.load()',view)
        self.assertIn('Custom URL is the login target when set',view)
if __name__=='__main__':unittest.main()
