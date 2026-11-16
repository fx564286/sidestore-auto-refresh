# P84 / L140 — 같은 해결 방식 반복 차단 + 실제 앱 진단 로그 프롬프트 내장

## 변경 목표

- 사용자가 지시한 139개 이력의 단순 코드 라인 중복 탐지에서 **실제 결과를 바꾸는 방법군 분류**로 강화.
- 기존 P13 단순 메커니즘 alias 및 새 device event로 인한 반복 예외는 P84 신규 후보에서 제거.
- L001~L139 실제 원본 이력·모든 before/after 보존. 신규 L140부터 추가 검증.
- 정상 기본 모드와 실험 상주 모드의 *화면 생성·컨트롤러 연결·렌더 표면 소유권·프로세스 Scene 생명주기*를 먼저 비교하는 3개 독립 가설을 프롬프트에 강제.

## 차단되는 해결 방법군

1. Safe Area/inset 재계산
2. 상태바 표시/숨김/스타일 보정
3. 헤더 frame/제약/transform 이동
4. 스크롤 inset/offset/viewport 이동
5. FBScene/원격 윈도우 crop/resize/transform
6. 시간 지연·retry·sampling 변경
7. overlay/chrome/window masking
8. 원래 레이아웃 훅 이후 header/content 위치 재적용

기존 이력의 ID를 명시한 규칙은 `rebuild/diagnostics/scarlet_distinct_strategy_gate.py`에 있으며 새 기기 로그로도 해제하지 않는다. 승인되지 않은 새 family 문자열로 우회하면 실패한다. 새 메서드가 기존 조작을 추가하는지 소스 diff도 점검한다. 정적 분석은 임의 코드의 완전한 의미상 동등성을 증명하지 않으므로 소스·반증 조건 검토는 계속 필요하다.

## 앱 로그 공유에 포함

`ScarletDiagnosticRecorder.makeShareFile()`은 현재 실행 로그보다 앞에 `P84 STRICT METHOD-FAMILY BAN`을 출력한다. 그 뒤 전체 L001~L140 원본 diff와 `SCARLET_LOG_ONLY_HANDOFF_PROMPT.md`의 한국어 지침을 base64 빌드 내장으로 포함한다. 최신 로그 한 개만 전달받아도 누적된 실패 방법과 3단계 실기기 확인 조건을 볼 수 있다.

## 검증 및 보호 범위

- 전체 Python 테스트: 833개 실행, 3 infra skip, 실패 0 (2026-11-16 로컬).
- 음성 반복 후보 재실행: 기존 `header_position_or_constraint` 시도는 새로운 로그를 붙여도 return code2 `HARD BLOCK`.
- 별도 신규 전략 메타데이터 요구사항, 정상/실험 모드 비교, 예외 없는 엄격한 분류와 인덱스 등 단위 테스트 통과.
- CI 3.8.84 원래 번들 ID `com.kdt.livecontainer.P8EZT3U5N4`, 원래 ShortVersion 3.8.11, 모든 확장 검사. 실기기 서명과 화면 정상화 증거 미확인.
- V48 원래 화면/스크롤/탭/색상, 계정 팀·설치 동작, Audio 및 Keyboard runtime 소스 수정 **없음**.

## 미해결과 다음 별도 코드 변경

P81 실기기 source `c5ad675b12d1`: PID553는 650ms 위험 컨트롤 9개 → native header retained 후 6개로 감소하나 body reflow는 reverted; 3550ms의 최초 y50/심각2 재발. P84는 같은 수정 방법 반복을 방지하는 빌드이며 **다이나믹 아일랜드 겹침 해결 빌드가 아니다**. 다음 실행 수정은 정상/실험 모드에서 실제 guest 생성·render attachment 소유권 차이를 소스 수준에서 재현·반증한 뒤 독립적 계약 오류만 고쳐야 한다.

소스 커밋: `725c1713a51a2f8763cc7a74157c7a42755d5f0a`.
