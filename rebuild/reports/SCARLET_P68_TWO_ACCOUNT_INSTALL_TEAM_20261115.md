# Scarlet Crystal P68 — Apple ID 두 계정의 설치팀 전환 / 실기기 진단

## P67 실제 증거 (user supplied, CURRENT RUN 8236de81)

- iOS 27.2, build 3.8.67, SourceCommit `1bc2e0b6bd85`.
- `auth.submit_tapped`, `twofactor_prompt_requested`, `twofactor_code_submitted`, `stored_session_verified`: Apple 2FA 후 인증 토큰 읽기 성공.
- `sidestore.install_failed`: `reason=team_mismatch`, `stage=team`, `worker_stage=certificate_loaded`. 즉, 원본 AppManager가 설치를 시도하기 전에 팀 검사에서 차단됐다.
- `refresh.manual_request_failed` 2회, `automatic_failure_categorized` 1회: `sidestore_team_mismatch`. 원인은 새 팀 선택 자체가 아니라, 일반 설치·갱신 요청에서도 기존 호스트 서명팀 `P8EZT3U5N4`만 허용하는 불필요한 코드 조건이다.
- 이 로그에는 두 번째 계정의 구체적인 팀 ID, 해당 팀 P12의 유효성 및 해당 계정으로 실제 앱을 설치한 성공 결과가 없다. 미확인 상태로 남긴다.

## P68 실행 경로

1. 설치 버튼 → **설치팀 선택** → 저장된 Apple ID / 그 계정의 검증된 개발팀 / 인증서 준비 상태 표시 → 선택 → 실제 IPA 파일 선택.
2. 별도 SideStore LiveProcess에 원본 Keychain·CoreData 계정 전환을 요청. 기존 A 토큰을 저장하고 B의 계정/팀을 복원하여 되읽는다.
3. 설치팀 준비 요청에서 선택된 팀의 실제 활성 로그인/Team ID와 인증서 leaf Subject의 exact Organizational Unit을 비교한다. 만료된 인증서·다른 팀 인증서·검증 불가능한 P12는 불합격 처리.
4. A/B 팀에 저장된 로컬 P12 중 일치하는 것을 원본 `CertificateManager.setActiveCertificate`로 설정. 인증서가 없으면 자동으로 타 팀 인증서를 강제 사용하는 대신 **선택한 설치팀 인증서 받기** 버튼(명시적 사용자 요청)을 제공. 기존 P12를 자동 삭제/폐기하지 않음.
5. `SideStoreSupport` → `XPCClient` → 설치 worker로 `expectedTeamID`를 전달하고, 파일 선택 후 계정이 바뀌었으면 실행을 거부. 원본 `AppManager.shared.install(.url(fileURL))`만 사용.
6. 동일 LiveProcess의 로그인/계정 전환/인증서 발급/설치/앱 갱신을 actor claim으로 직렬화해, 서명 도중 계정이 바뀌는 경쟁 조건을 차단.
7. 수동·자동 SideStore refresh는 원본 CoreData의 `InstalledApp.team`과 선택한 개발팀을 교차검증해 **선택 팀의 앱만** 갱신. B 팀에서 A의 Scarlet 호스트 재서명 금지. A 팀의 기존 signed host 관리 정보가 없는 경우에도 타인 앱을 임의로 갱신하지 않도록 제한.
8. 호스트의 기존 Apple 서명 entitlement / App Group / Bundle ID 검사는 보존한다. 앱 설치 시 사용자 개발팀을 달리 선택하는 것과, 이미 서명되어 설치된 Scarlet 호스트 자체의 Apple Team은 별개의 개념이다.

## 수락 기준

- 계정 A/B 각자 정상 2FA와 설치팀 목록 표시.
- A→B→A 전환 후 계정별 token/team/certificate readback. 다른 팀 인증서로 설치 불가.
- B로 별도 IPA 설치 요청 시 `team_mismatch` 대신, 원본 AppManager 서명·기기 설치 경로까지 도달하거나 **정확한 인증서·계정 오류** 반환.
- 앱 갱신은 선택된 팀의 관리 앱만 대상으로 하고 설치되지 않은 호스트의 갱신 성공을 허위 기록하지 않음.
- 저장된 원본 인증서/게스트 IPA/페어링 기록/로그인 A는 임의로 삭제하지 않음.
- P67 화면, 상단 안전 영역, 상태 표시줄, 스위처 등 UI 변경 금지. P67 로그에 남은 화면 문제는 별도 미해결.

## 검증 경계

P68 Python 회귀 테스트는 코드 경로 증빙이고, Apple 실기기 로그인·서명·설치 성공 증거는 아니다. Xcode iOS 네이티브 CI 빌드와 서명된 iPhone에서 A/B 팀 설치 및 갱신 테스트로 추가 검증해야 한다.
