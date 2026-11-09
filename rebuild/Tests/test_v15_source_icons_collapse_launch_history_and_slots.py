"""V15 regression protection: collapsed source, true icons, pre-handoff A/B,
and original shortcut transport dependencies."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
UI=(R/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(R/"HostApp/ScarletIntegratedHostView.swift").read_text()
LEDGER=(R/"HostApp/ScarletGuestSessionLedger.swift").read_text()
PACK=(R/"integration/package_paired.py").read_text()
VERIFY=(R/"integration/verify_engines.py").read_text()
AUD=(R/"scripts/audit_appid_footprint.py").read_text()

class V15(unittest.TestCase):
    def test_source_collapsed_by_default(self):
        self.assertIn('@State private var expandedSourceIDs: Set<String> = []',UI)
        self.assertIn('if expandedSourceIDs.contains(source.id) {',UI)
        self.assertIn('SCARLET_SOURCE_DISCLOSURE',UI)
        self.assertIn('chevron.down',UI)
        self.assertIn('Button { onOpenSource(source.id) }',UI)
        self.assertIn('Button(action: onAddSource)',UI)
        self.assertIn('ForEach(source.apps)',UI)
        self.assertLess(UI.index('if expandedSourceIDs.contains(source.id) {'),
                        UI.index('ForEach(source.apps)'))

    def test_source_icon_url_mapped_from_actual_source_data(self):
        self.assertIn('public let iconURL: URL?',UI)
        self.assertIn('AsyncImage(url: app.iconURL)',UI)
        self.assertIn('SCARLET_SOURCE_APP_ICON',UI)
        self.assertIn('iconURL: app.iconURL',HOST)
        self.assertIn('Image(systemName: "app.fill")',UI)

    def test_history_saved_before_nonreturning_launch_and_rollback(self):
        anchor=HOST.index('// V14 registered AFTER await runApp')
        launch=HOST.index('try await app.runApp()',anchor)
        save=HOST.index('ScarletGuestSessionLedger.noteLaunch(',anchor)
        self.assertLess(save,launch)
        self.assertIn('ScarletGuestSessionLedger.restore(historyBeforeLaunch)',HOST)
        self.assertGreaterEqual(HOST.count('ScarletGuestSessionLedger.restore(historyBeforeLaunch)'),2)
        self.assertIn('session_history_pre_handoff',HOST)
        self.assertIn('static func restore(_ entries: [Entry])',LEDGER)
        self.assertIn('Scarlet.Guest.RecentSessions.V14',LEDGER)

    def test_no_silent_shortcuts_regression_from_share_removal(self):
        self.assertIn('RELEASE_EXTENSIONS=EXTENSIONS',PACK)
        self.assertIn('LaunchAppExtension relies on the original ShareExtension',PACK)
        self.assertNotIn('shutil.rmtree(optional_share)',PACK)
        self.assertIn('RELEASE_EXTENSIONS=EXTENSIONS',VERIFY)
        self.assertIn('ShareExtension.appex/',VERIFY)
        self.assertIn('"ShareExtension": HOST_ID + ".ShareExtension"',AUD)
        self.assertIn('types["ShareExtension"]',AUD)

if __name__=="__main__":unittest.main()
