# P86 / L143 — P85 전체 로그 P0 분석 및 계정별 Apple 인증서 직접 발급

## 실기기 근거

- P85 3.8.85, source `44abc545d1e0`, current launch `e611a5a1`, 2026-11-16: 207 JSONL events, success24, blocked3, warning2, error0.
- 자동 갱신: `automatic_managed_apps_inspected` seq25/189/200 모두 `count=0`, `reason=host_selected_team_mismatch`. 활성 Apple 팀 B와 원래 설치된 A팀 Scarlet 서명팀이 다름. 별도 B팀 인증서 발급만으로 호스트 A팀 자동 갱신 차단은 해결되지 않음.
- 계정: `settings_account_switch_verified` seq170/174 두 번 success. `certificate` 계열 발급 이벤트는 0건: 기존 P68 발급 함수가 P82 로그인/전환/설치 경로에서 호출되지 않았음.
- 화면: PID4730 최초 상단 위험 컨트롤 9개, 2600ms 6개. 2850/3550ms severe_nodes=0 상태로 두 번 연속 확인됐지만 `status_hidden=true`가 seq141/142에서 유지돼 상태바 복귀 실패. 전체 앱 UI 겹침 미해결.
- 오디오: device pause/resume ACK 존재. 물리적 오디오 격리 자체는 입증되지 않음.

## 실제 발급 실패의 구조적 원인

기존 소스에는 `ScarletNativeSavedAccounts.issueInstallCertificate`와 Apple 팀 권한 검증이 이미 있었지만, Settings account switch와 P82 install path는 `prepareInstallTeam`만 호출. 원본 SideStore `CertificateProvisioningFlow`는 foreign active cert를 custom cert로 처리하고 반환하므로, 팀 A 인증서가 활성일 때 B 포털 신규 발급이 건너뛰어질 수 있었음. SideInstaller는 Apple `submitDevelopmentCSR`를 직접 사용; 해당 원본 SideStore의 `DeveloperPortalProxy.createCertificate`로 독립적인 발급 절차 구현.

## P86 코드 조치

1. 현재 활성 Apple ID의 개발팀을 Keychain/SideStore 저장계정에서 재확인하고 유효한 기존 팀 P12를 재사용.
2. 기존 유효 개인키가 없으면 해당 팀 Apple Developer Portal 인증서 조회 후 기존 일치 키 재사용 시도, 실패 시 신규 인증서 직접 발급, 팀 OU/유효기간/Keychain 저장·읽기 검증.
3. 설정 계정 전환·추가 로그인 이벤트와 IPA 설치 버튼에서 동일한 준비 코드를 호출. 두 번째 계정 선택 UI 없음.
4. native `ScarletTeamOperationGate`는 XPC 응답 이전에 잠금 해제해 연달아 발생하는 prepare→issue→prepare를 안전하게 수행. 계정 전환 중 발급 동시 실행은 차단.
5. 로그: `account_certificate_preflight_started`, `account_certificate_team_readback`, `install_selected_team_certificate_result`와 `ready_existing`, `ready_existing_portal`, `ready_issued_apple`, `selected_team_certificate_quota_reached`, `selected_team_certificate_storage_failed` 구분. 원본 비밀·개인키/시리얼 미기록.

## 검증 범위

Python 843개 실행(3개 infra skip), 0 실패; no-repeat proposal passed. Xcode27.2 네이티브 컴파일 및 Apple 포털 신규 발급·실기기 설치 결과는 미확인. 원래 V48 레이아웃, P85 계정 구분선 소스, 계정 분리, SideStore AppManager 설치 엔진 유지. **서명팀이 다른 원래 Scarlet 호스트의 자동 갱신, 다이나믹 아일랜드, 상태바 복원은 별도 미해결**.

Source commit `0e2d913ea23138e0839dec2475e2858981f53804`.
