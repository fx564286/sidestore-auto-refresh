"""P69: single-owner settings actions, no redundant passive labels.
This checks source/UI contracts; device visuals require signed iPhone proof.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
PANEL=(R/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
PATCH=(R/'integration/apply_scarlet_host.py').read_text()
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
LOGIN=(R/'HostApp/ScarletAppleIDLoginSheet.swift').read_text()

class SettingsDebloat(unittest.TestCase):
    def test_refresh_status_is_single_recent_receipt_when_present(self):
        self.assertIn('@State private var lastRefreshAttemptState: String = "기록 없음"', PANEL)
        self.assertIn('if lastRefreshAttemptState != "기록 없음"', PANEL)
        self.assertIn('LabeledContent("최근 갱신", value: displayRefreshState)', PANEL)
        for redundant in ('LabeledContent("자동 갱신",', 'LabeledContent("자동 갱신 대상",',
                          'LabeledContent("이 앱 자동 갱신",', 'LabeledContent("갱신 문제",',
                          'LabeledContent("서명 상태",'):
            self.assertNotIn(redundant, PANEL)
        self.assertIn('SCARLET_NATIVE_REFRESH_NOW', PANEL)
        self.assertIn('sidestore_managed_apps_inspected', PANEL)
        self.assertIn('ScarletRefreshFailureDiagnosis.nativeGuidance', PANEL)
        self.assertIn('if let lastRefreshFailureReason, statusMessage == nil', PANEL)
    def test_auth_shows_single_login_and_no_repeated_signing_badge(self):
        self.assertIn('Label("로그인됨", systemImage:', PATCH)
        self.assertIn('SCARLET_SETTINGS_ADD_LOGIN', PATCH)
        self.assertNotIn('scarletSigningCertAvailable', PATCH)
        self.assertIn('SCARLET_STORED_LOGIN_VISIBLE', LOGIN)
        self.assertIn('Button("추가 로그인")', LOGIN)
        self.assertNotIn('SideStore 보안 저장소에서 Apple 인증 토큰을 확인했습니다.', LOGIN)
    def test_one_certificate_panel_keeps_actual_actions(self):
        self.assertIn('ScarletSigningReadinessPanel()', PATCH)
        self.assertIn('SCARLET_P12_NATIVE_ISSUE', PANEL)
        self.assertIn('SCARLET_P12_IMPORT_FROM_FILES', PANEL)
        self.assertNotIn('SCARLET_SELECT_INSTALL_TEAM', LOGIN)
        self.assertNotIn('SCARLET_ISSUE_SELECTED_TEAM_CERT', LOGIN)
        self.assertNotIn('인증서 저장됨', LOGIN)
        self.assertIn('selected_team_certificate_missing', HOST)
    def test_no_false_multiteam_information_and_preserve_slot_manager(self):
        self.assertNotIn('다른 계정을 등록해도 설치 팀이 자동 변경되지는 않습니다', HOST)
        self.assertNotIn('기기 검증 전', HOST)
        self.assertIn('SCARLET_NATIVE_SLOT_MANAGER_OPEN', Path(__file__).resolve().parents[1].joinpath('integration/apply_scarlet_host.py').read_text())
        self.assertIn('SCARLET_NATIVE_SLOT_MANAGER_SHEET', HOST)
        self.assertIn('install_active_team_prepared', HOST)

if __name__=='__main__': unittest.main()
