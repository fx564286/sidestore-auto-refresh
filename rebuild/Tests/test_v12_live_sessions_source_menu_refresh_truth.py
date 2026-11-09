"""V12 regressions: actual live sessions, source-specific menu, refresh truth."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
GUEST=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
CERT=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()

class V12LiveTruth(unittest.TestCase):
    def test_no_phantom_installed_guest_rows(self):
        self.assertIn('ScarletGuestSceneRegistry.availableGuests().map(\\.id)',GUEST)
        self.assertIn('guard isCurrent || activeScene || recentFolders.contains(folder)',GUEST)
        self.assertIn('activeSceneIDs.contains($0)',GUEST)
        self.assertIn('MultitaskManager.isUsing(container: $0)',GUEST)
        self.assertIn('apps.filter { !$0.isCurrent }',GUEST)
        self.assertIn('"result": "live_and_launched_history"',GUEST)
        self.assertNotIn('currentAppCard',GUEST)
        self.assertIn('SCARLET_GUEST_CURRENT_RUNNING',GUEST)

    def test_no_silent_guest_kill_switching(self):
        segment=GUEST.split('private static func switchGuest(to target:',1)[1].split(
            '    @objc(installForGuestName:)',1)[0]
        self.assertIn('switch_existing_multitask_session',segment)
        self.assertIn('switch_requires_relaunch',segment)
        # Resident scenes are reused without restart; only unavailable
        # cold targets take the explicitly guarded original LC handoff.
        self.assertIn('if latest.canSwitch, let container = latest.containerID',segment)
        self.assertIn('guard latest.canRelaunch',segment)
        self.assertIn('let submitted = LCSharedUtils.launchToGuestApp(',segment)
        self.assertIn('switch_cold_handoff',segment)
        self.assertNotIn('defaults.set(target.id',segment)
        self.assertIn('return false',segment)
        self.assertIn('LCSharedUtils.launchToGuestApp(withClassicMode: 0)',GUEST) # explicit exit only

    def test_source_ellipsis_only_manages_selected_source(self):
        self.assertIn('selectedSourceURL = source.id',HOST)
        self.assertIn('source_actions_opened',HOST)
        self.assertIn('originalSources.refreshSource(item)',HOST)
        self.assertIn('originalSources.removeSource(item)',HOST)
        self.assertIn('"소스만 삭제"',HOST)
        self.assertIn('이미 설치한 게스트 앱과 앱 데이터는 유지',HOST)
        self.assertNotIn('LCSourcesView()',HOST)
        self.assertIn('onAddSource: {',HOST)

    def test_refresh_does_not_claim_success_when_only_preflight(self):
        self.assertIn('LabeledContent("자동 갱신",',CERT)
        self.assertIn('"Scarlet.Refresh.LastAttemptOutcome"',CERT)
        self.assertIn('lastRefreshAttemptState',CERT)
        self.assertIn('"요청 반환 · 재설치 확인 안 됨"',CERT)
        self.assertIn('"실패 · SideStore 갱신 오류"',CERT)
        self.assertNotIn('BGTaskScheduler.shared.register(',CERT)
        self.assertIn('"manual_request_underlying_error"',CERT)

if __name__=='__main__':unittest.main()
