"""P57: original LiveContainer visible options remain, hidden Scarlet worker never blocks."""
import ast
import tempfile
import shutil
import unittest
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
GEN=(ROOT/"integration/apply_scarlet_host.py").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
WF=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
START=GEN.index('def apply_queued_guest_overwrite_source(')
END=GEN.index('def hide_embedded_sidestore_guest_navigation(',START)
PATCH=GEN[START:END]
class P57Overwrite(unittest.TestCase):
    def test_original_lc_replace_alert_only_visible_not_hidden(self):
        self.assertIn('if scarletQueuedIPAURL != nil {',PATCH)
        self.assertIn('if sameBundleIdApp.count > 1 {',PATCH)
        self.assertIn('if let existing = sameBundleIdApp.first {',PATCH)
        self.assertIn('guard !existing.isAppRunning else {',PATCH)
        self.assertIn('overwrite_single_match_selected',PATCH)
        self.assertIn('guard let selected = await installReplaceAlert.open()',PATCH)
        self.assertIn('installOptionChosen = selected',PATCH)
        self.assertIn('if installOptionChosen.isReplace && scarletQueuedIPAURL == nil',PATCH)
    def test_never_delete_old_app_before_sign_ready(self):
        self.assertIn('let scarletTransactionalReplace =',PATCH)
        self.assertIn('try fm.moveItem(at: appFolderPath, to: scarletStageFolder)',PATCH)
        self.assertIn('!signSuccess && !finalNewApp.dontSign',PATCH)
        self.assertLess(PATCH.index('try fm.moveItem(at: appFolderPath, to: scarletStageFolder)'),
                        PATCH.index('!signSuccess && !finalNewApp.dontSign'))
        self.assertLess(PATCH.index('!signSuccess && !finalNewApp.dontSign'),
                        PATCH.index('try fm.moveItem(at: outputFolder, to: backupFolder)'))
    def test_same_volume_swap_rolls_back_without_erasing_guest_data(self):
        for marker in (
             'let backupFolder = outputFolder.deletingLastPathComponent()',
             'try fm.moveItem(at: outputFolder, to: backupFolder)',
             'try fm.moveItem(at: scarletStageFolder, to: outputFolder)',
             'readback.dataUUID == previous.appInfo.dataUUID',
             'finalNewApp.setBundlePath(outputFolder.path)',
             'try fm.moveItem(at: backupFolder, to: outputFolder)',
             'overwrite_rollback_restored', 'overwrite_rollback_failed',
             'overwrite_committed', 'overwrite_sign_failed_preserved',
             'overwrite_target_changed'):
            self.assertIn(marker,PATCH,marker)
        for forbidden in ('try fm.removeItem(at: previous.appInfo', 'deleteGuestData',
                          'LCPath.dataPath', 'appToReplace.appInfo.containerInfo = nil'):
            self.assertNotIn(forbidden,PATCH)
    def test_user_sees_failure_without_extra_hidden_alert(self):
        self.assertIn('@Published private(set) var failureDetail: String?',HOST)
        self.assertIn('failureDetail: String? = nil',HOST)
        self.assertIn('case .failed: return failureDetail ??',HOST)
        self.assertIn('failureDetail: errorShow ? errorInfo : nil',GEN)
        self.assertIn('scarlet-v48-r6p57-guest-overwrite-unsigned-20261114',WF)
    def test_generator_is_syntax_valid_and_applies_to_pinned_upstream_if_present(self):
        ast.parse(GEN)
        pinned=Path('/tmp/scarlet-lc-pinned-20261109/LiveContainerSwiftUI/Views/AppList/LCAppListView.swift')
        if not pinned.exists():
            self.skipTest('Pinned LC only available during native CI checkout/integration')
        spec=importlib.util.spec_from_file_location('scarlet_apply57',ROOT/"integration/apply_scarlet_host.py")
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory(prefix='scarlet-p57-fixture-') as tmp:
            engine=Path(tmp)
            target=engine/'LiveContainerSwiftUI/Views/AppList/LCAppListView.swift'
            target.parent.mkdir(parents=True)
            shutil.copy2(pinned,target)
            receipt=mod.hide_embedded_sidestore_guest_navigation(engine)
            out=target.read_text()
            self.assertIn('overwrite_single_match_selected',out)
            self.assertIn('overwrite_committed',out)
            self.assertIn('overwrite_rollback_restored',out)
            self.assertIn('let scarletTransactionalReplace',out)
            self.assertIn('failureDetail: errorShow ? errorInfo : nil',out)
            self.assertNotIn('LCUtils.openSideStore(',out)
            self.assertEqual(receipt['appManager'],'LCAppListView')
if __name__=='__main__':
    unittest.main()
