"""V32: no raw status-code wording in pairing Settings UI.
The operational pairing verification is unchanged; its log receipts remain
canonical, while users see concise, natural Korean.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PAIR=(ROOT/"HostApp/ScarletNativeDevicePairing.swift").read_text()
SETTINGS=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
WORKER=(ROOT/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()

class V32KoreanCopy(unittest.TestCase):
    def test_pairing_positive_status_is_exact_requested_copy(self):
        self.assertIn('savedRecordState = ready ? "페어링 됨"', PAIR)
        self.assertIn('phase = "페어링 됨"', PAIR)
        self.assertIn('self.savedRecordState = ok ? "페어링 됨"', PAIR)
        self.assertIn('self.phase = ok ? "페어링 됨"', PAIR)
        self.assertNotIn('페어링 유지됨', PAIR)
        self.assertNotIn('연결 검증됨', PAIR)
        self.assertNotIn('페어링 저장됨', PAIR)
        self.assertNotIn('연결 상태 확인 필요', PAIR)

    def test_states_are_short_accurate_and_not_faux_success(self):
        for s in ('"확인 중"','"페어링 필요"','"페어링 중"','"연결 확인 필요"'):
            self.assertIn(s, PAIR)
        self.assertIn('reason == "pairing_file_missing" ?', PAIR)
        self.assertIn('verified = ready', PAIR)
        self.assertIn('pairing_state_unverified', PAIR)
        self.assertIn('guard !active && !stateReadInFlight', PAIR)
        self.assertIn('func errorDescription(for reason: String)', PAIR)
        self.assertIn('pairing.errorDescription(for: reason)', PAIR)
        self.assertNotIn('LabeledContent("연결 오류", value: reason)', PAIR)

    def test_single_sheet_compact_copy_and_semantics(self):
        self.assertIn('LabeledContent("상태", value: pairing.savedRecordState)', PAIR)
        self.assertIn('if pairing.active || pairing.phase != pairing.savedRecordState', PAIR)
        self.assertIn('Label("페어링 설정"', SETTINGS)
        self.assertIn('Label(pairing.active ? "페어링 중"', PAIR)
        self.assertIn('pairing.verified ? "다시 페어링" : "페어링 시작"',PAIR)
        self.assertIn('.navigationTitle("페어링")', PAIR)
        self.assertNotIn('Text("기존 SideStore 갱신 엔진과 연결이 확인됐습니다.")', PAIR)

    def test_refresh_receipt_kept_honest_but_korean_plain(self):
        self.assertIn('Text("앱 갱신 중")', SETTINGS)
        self.assertIn('LabeledContent("자동 갱신 대상"', SETTINGS)
        self.assertIn('Text("서명 및 페어링")', SETTINGS)
        self.assertIn('"갱신 작업은 끝났지만, 실제 설치 완료는 확인되지 않았습니다."', SETTINGS)
        self.assertIn('native_operation_returned_unverified', WORKER)

if __name__=='__main__':unittest.main()
