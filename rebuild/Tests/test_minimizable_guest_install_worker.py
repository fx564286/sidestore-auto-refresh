"""Regression contracts: dismiss progress UI without ending an in-app install.

The real LiveContainer import worker is retained under the Scarlet host,
independent from either sheet. No simulation here pretends that a guest ran
on-device or that iOS will continue work when Scarlet is suspended.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class MinimizedGuestInstall(unittest.TestCase):
    def test_host_owns_worker_not_the_sheet(self):
        before_sheet = HOST.split('.sheet(isPresented: $showGuestImportProgress',1)[0]
        guest_sheet = HOST.split('.sheet(isPresented: $showGuestImportProgress',1)[1].split(
            '.sheet(isPresented: $showSourceURLInput',1)[0]
        self.assertIn('SCARLET_HIDDEN_GUEST_IMPORT_WORKER',before_sheet)
        self.assertIn('LCAppListView(scarletQueuedIPAURL: queuedGuestIPAURL,',before_sheet)
        self.assertIn('scarletActivity: guestImportActivity',before_sheet)
        self.assertNotIn('LCAppListView(',guest_sheet)
        self.assertNotIn('removeItem(at:',guest_sheet)
        self.assertIn('.presentationDragIndicator(.visible)',guest_sheet)
        self.assertNotIn('.interactiveDismissDisabled()',guest_sheet)

    def test_worker_cleans_up_only_after_original_importer_returns(self):
        self.assertIn('scarletActivity?.finish(',PATCH)
        self.assertIn('scarletOnImportFinished?()',PATCH)
        self.assertIn('scarletOnImportFinished: guestImportWorkerFinished',HOST)
        self.assertIn('private func guestImportWorkerFinished()',HOST)
        self.assertIn('queuedGuestIPAURL = nil',HOST)
        self.assertIn('defer { installprogressVisible = false }',PATCH)
        self.assertIn('onChange(of: installProgressPercentage)',PATCH)
        self.assertNotIn('completed_sheet_auto_closed',PATCH)

    def test_download_survives_minimize_and_handoff_remains_reachable(self):
        self.assertIn('sourceDownloadTask = Task { @MainActor in',HOST)
        self.assertIn('if showSourceDownloadSheet {',HOST)
        self.assertIn('handoffDownloadedSourceIfReady()',HOST)
        self.assertIn('stageGuestIPAFromFiles(staged, presentProgress: !installProgressMinimized)',HOST)
        download_sheet = HOST.split('.sheet(isPresented: $showSourceDownloadSheet',1)[1].split(
            '.sheet(isPresented: $showNativeSources',1)[0]
        self.assertIn('download_kept_alive',download_sheet)
        self.assertIn('Button(sourceIsDownloading ? "내리기" : "닫기")',download_sheet)
        self.assertIn('sourceDownloadTask?.cancel()',download_sheet)
        self.assertIn('.presentationDragIndicator(.visible)',download_sheet)
        self.assertNotIn('.interactiveDismissDisabled(sourceIsDownloading)',download_sheet)

    def test_parallel_browsing_reopen_progress_without_new_hud(self):
        self.assertIn('SCARLET_REOPEN_MINIMIZED_INSTALL',UI)
        self.assertIn('activeInstallRow',UI)
        self.assertIn('onShowActiveInstall: openActiveInstallProgress',HOST)
        self.assertIn('activeInstallText: sourceIsDownloading',HOST)
        self.assertIn('sourceIsDownloading || !guestImportActivity.isRunning',HOST.replace(
            'guard !sourceIsDownloading, !guestImportActivity.isRunning,',
            'sourceIsDownloading || !guestImportActivity.isRunning'))

    def test_no_claim_of_guest_execution_or_extra_glass_overlay(self):
        self.assertIn('imported_launch_unverified',HOST)
        self.assertNotIn('onShowActiveInstall: { showNativeSources',HOST)
        self.assertNotIn('.overlay(alignment: .top) {\n            if sourceIsDownloading',HOST)
        self.assertIn('presentationBackground(Color(red: 0.14',HOST)

if __name__=="__main__":
    unittest.main()
