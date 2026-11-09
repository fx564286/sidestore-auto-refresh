"""Keep user-approved Scarlet UI labels stable across auth/entitlement fixes.

Functional state may change, but the action label and navigation copy remain
identical; additional diagnostic information lives in independent status text.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
CAP=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class UserVisibleLabelStability(unittest.TestCase):
    def test_apple_id_action_label_does_not_change_with_auth_state(self):
        self.assertIn('Label("Apple ID 로그인",',PATCH)
        self.assertNotIn('Apple ID 로그인됨 · 계정 관리',PATCH)
        self.assertNotIn('Apple ID 확인 중',PATCH)
        self.assertIn('로그인됨 · 내장 SideStore 세션 복원',PATCH)

    def test_original_settings_and_manual_refresh_labels_are_preserved(self):
        for label in (
            'LabeledContent("앱 그룹 권한",',
            'LabeledContent("개발 팀·앱 식별자",',
            'LabeledContent("LiveContainer 서명 인증서",',
            'LabeledContent("자동 갱신",',
            'Label("SideStore 수동 새로고침",',
        ):
            self.assertIn(label,CAP)
        self.assertNotIn('LabeledContent("App Group 서명 권한",',CAP)

    def test_original_upstream_certificate_alert_not_overwritten(self):
        self.assertNotIn('source=source.replace(certificate_misleading',PATCH)
        self.assertIn('Preserve upstream localized certificate alerts verbatim',PATCH)

    def test_app_navigation_and_diagnostics_labels_are_stable(self):
        self.assertIn('heading("", "설치된 앱", "")',UI)
        self.assertIn('TextField("설치된 앱 검색", text: $searchText)',UI)
        self.assertIn('Label("소스 추가", systemImage: "plus")',UI)
        self.assertIn('.alert("Scarlet Crystal 진단", isPresented:',HOST)

if __name__=="__main__":
    unittest.main()
