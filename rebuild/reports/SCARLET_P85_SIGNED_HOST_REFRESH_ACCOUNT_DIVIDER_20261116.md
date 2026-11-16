# P85 — P84 실기기 로그 우선 갱신 차단 원인 수정 + 계정 구분선

## P84 실기기 기록
- Build 3.8.84, SourceCommit `3aec1a705045`, Session `172d5052`.
- seq24 `pairing_restored=success`; seq25 `automatic_managed_apps_inspected`, `reason=host_bundle_path_unavailable`, count0, blocked; seq28 `certificate_preflight` signed host identity/team match.
- 원인: P73/P76 내장 LiveProcess Swift worker는 guest class bundle / argv[0]에서 `.appex/PlugIns`로 역추적했으나, 실제 호스트 설치 경로를 전달받지 못했음. Host XPC에서 호출자가 가진 원래 서명된 호스트 `Bundle.main.bundleURL`을 전달하면 Swift worker가 경로를 추론하지 않아도 검증 가능.
- P85는 호스트 원본 설치 경로를 기존 XPC `scarletRefreshReadiness`/`scarletPerformNativeRefresh`로 전달. `inspectHostBundle:reply:`와 `performHostBundle:reply:` 호출 후 앱 확장·embedded.mobileprovision·앱 bundle ID·provisioning team·선택 team·인증서·원본 SideStore cache/InstalledApp CoreData 검증을 통과할 때만 관리 앱 등록. 데이터 삭제·서명팀 임의 변경·가짜 갱신 결과 없음.
- 자동 갱신 상태는 여전히 작업자 실제 결과에 따름. count0이 계속되면 다음 오류를 추적하고 성공이라고 주장하지 않음.

## 계정 UI
- P84 iPhone 스크린샷의 현재 계정 오른쪽 아래 단독 짧은 divider 수정. 여러 계정을 하나의 native Form row 소유 VStack으로 묶고 인접 계정 사이 전체 폭 Divider 한 개만 그려 화면 불일치를 제거.
- `사용 중`/`전환`, 기존 Keychain 계정 활성화, 추가 로그인, 진단 로그 공유 유지.

## 검증과 미해결
- 로컬 Python 838 테스트, 3 infra skips, 실패0. `L141`,`L142` 별도 사전 중복 수정 검사 통과.
- Xcode27.2 네이티브 빌드·IPA 릴리스·서명 실기기 갱신 결과와 화면은 별도 검증.
- P84 로그의 실험 모드 다이나믹 아일랜드·상태바 충돌(guest PID 2556/2570), 오디오·RAM 상태 등 이번 호스트 등록 수정과는 별도 미해결. 앱의 기존 V48 레이아웃·P82 계정 설치·서명·게스트 데이터 변경 없음.

소스 커밋 `55365911ebfa842e1f7eb48bbbea11cdaaba89bd`.
