# Scarlet Crystal P102 — 계정별 소유권·인증서 오류·갱신 대상 분리

## 기준 및 현재 실기기 증거
- 소스 기준: P101 cb87186b2897002f8b2066a8572dfda8c0da3dfe.
- 사용자 제공 P101 실기기: certificate_bridge_imported, signature_valid, 게스트 PID 834 화면 연결, 계정 전환 4회, 오디오 재개·정지 응답 ok.
- 미해결: 두 로그인 계정의 소유권/표시 구분, 신규 Apple 인증서 발급 4회 실패, 관리 앱 0개, 위험 컨트롤 5개와 상태바 숨김.
- P101 로그는 로그인 성공 근거이지 계정별 앱·인증서 소유권 격리 근거는 아니다.

## 소스에서 확인된 근본 원인
1. ScarletGuestSignInAgent.ensureActiveTeamForRefresh는 원본 CoreData에서 Account.identifier와 Team.identifier만으로 객체를 찾고 기존 Account.appleID를 새 이메일로 덮어쓸 수 있었다. Team.account 관계 일치 검증도 빠져 있었다.
2. 원본 SideStore AltStore 17_7 데이터 모델은 Account.identifier, Team.identifier 각각 전역 고유키를 사용한다. 따라서 서로 다른 Apple ID가 하나의 Team ID를 공유하면 Team을 2개 독립 객체로 만들 수 없다. 조용히 Team을 이전 계정에서 새 계정으로 재귀속하면 관리 앱까지 섞인다.
3. Settings의 인증서 준비 확인은 Team ID만 비교해 같은 Team 소속의 다른 Apple ID를 구별하지 못했다.
4. 설정의 Apple 계정 목록은 이메일/활성 상태만 보여주고 관리 앱과 인증서의 독립 소유권을 표시하지 않았다.
5. 원본 SideStore fetchAppsForRefreshingAll은 비활성 앱 등을 필터링하므로 반환 0건만으로 DB 미등록을 확정할 수 없다.

## P102 수정 후보
- Apple ID와 Team의 실제 CoreData 관계 및 저장된 Keychain 로그인 ID/토큰을 전환 후 재검증한다. 서로 다른 Apple ID에 동일한 계정/Team 고유 객체가 연결되면 명시적으로 차단한다.
- 계정별 관리 앱 수는 원본 CoreData InstalledApp.team.account와 정확한 Apple ID+Team 조합으로 집계한다. 계정별 원본 서명 인증서의 저장·유효성도 별도 확인한다.
- 설정 및 로그인 화면의 기존 계정 행 안에 이메일, Team, 서명 인증서 상태 및 관리 앱 수를 각각 보여준다. 불필요한 섹션·구분선은 늘리지 않는다.
- Apple 포털 신규 인증서 발급 오류 단계(preflight/create/readback/import_lookup), NSError 도메인/코드/원인 코드를 안전한 XPC 진단 필드로 남긴다. 사용자 계정 ID, P12, 암호, 토큰, Apple 응답 문자열을 기록하지 않는다.
- 갱신 대상 0건을 실제 미등록, 모두 비활성, 원본 갱신 필터 제외, DB 조회 실패로 구분한다.
- P101 게스트 서명·커널 검증·화면 연결·멀티태스킹·오디오·상태바 위험 방어 정책은 변경하지 않는다.

## 판정 조건
1. 실기기 P102에서 A→B→A 전환 후 서로 다른 Apple ID/Team에 맞는 인증서 및 관리 앱 수가 표시되고 활성 계정은 항상 정확히 하나.
2. 계정 B가 계정 A의 관리 앱·인증서를 소유한 것처럼 표시되거나 재서명하지 않아야 한다.
3. 두 Apple ID의 Team ID가 동일하면 원본 SideStore DB의 고유키 충돌을 분명히 표시하고 다른 계정 Team/InstalledApp을 덮어쓰지 않는다. 이 경우 완전 분리에는 원본 CoreData 스키마·마이그레이션 변경이 필요하다.
4. 인증서 신규 발급 실패 시 error_stage/domain/code가 남고 실제 성공 증명 없이 성공 표시하지 않는다.
5. 실기기 JIT-less signature_valid와 guest PID, 상태바 위험 컨트롤·시계/배터리, 계정별 갱신 및 오디오 상태를 회귀 확인한다.

## 검증 사실
- P102 변경 후 전체 로컬 Python 회귀검사 926건 실행, 실패 0건, 4건 skip. 정적 계약 검사이며 native Xcode/iPhone의 실제 동작 증명이 아니다.
- P102 서명 실기기 결과, Apple 신규 인증서 발급, 실제 자동·수동 갱신 및 상단 UI 해결 여부는 검증되지 않았다.
