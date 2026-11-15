# Scarlet Crystal P73 — P71 실기기 CURRENT RUN `e7091b0f` 원인·코드 수정

## 원본 실기기 근거

- 기기: iOS 27.2 (24B119), 빌드 3.8.71, SourceCommit aadd4ce2325b. Current launch `2026-11-15 07:18:12 +0000`; 정확히 **198개 이벤트**.
- `07:18:12.702Z` `pairing_restored` = `pairing_saved_and_transport_ready`. P72의 timeout bypass가 이번 차단 원인은 아님.
- `07:18:12.969Z` 및 `07:19:33.565Z` `automatic_managed_apps_inspected` = `count:0`, `no_managed_apps_for_selected_team` (총 2회). 원본 SideStore CoreData에 해당 선택팀의 갱신 대상이 없음.
- `settings_account_switch_verified` 총 4회. Apple 계정 전환 경로는 성공 기록; 화면에서 눈으로 A/B가 표시되는지 별도 검증 필요.
- `certificate_preflight`: cert present, entitled App Group accessible, signed host team match. **호스트 LC 인증서 검사는 SideStore 관리 앱 등록 증거가 아님**.
- 게스트 PID 4252 remote scene attach/foreground, safeTop62, guest-root 62. 650ms unsafe visible controls 8, 2600ms 5. 상단 시계·배터리는 `status_hidden=true` 계속. P73에서 건드리지 않음(기존 P51/56/65 미해결 여전히).
- `guest_audio_device_receipt=ok`는 호스트↔게스트 제어 요청 ACK; 이어폰/스피커 실기기 무음 검증은 별도.
- `installed_profile_changed_after_request`는 installed profile digest 변화만 나타내고 `installation_verified=false`; 자동 설치 성공으로 취급하면 안 됨.

## 실제 pinned SideStore (ee3cc16a67f9) 코드 대조

1. `AltStore/Core/Model/DatabaseManager/DatabaseManager.swift`: `prepareDatabase()`는 `Bundle.isAppExtension()`에서 즉시 return. Scarlet는 SideStore를 **LiveProcess.appex** 안에서 실행하므로 start() 호출만으로 signed Scarlet host 자체가 `InstalledApp`으로 생성되지 않음.
2. `AltStore/Core/Model/InstalledApp.swift`: `fetchAppsForRefreshingAll`은 실제 `InstalledApp.isActive` 레코드만 선택. 로그인·페어링 정상 여부와 무관하게 CoreData 0개면 refresh를 진행하지 않음.
3. `SideStore/Core/Operations/PipelineOperations/CacheAppOperation.swift`: `cachePayload(for:)`는 원본 앱 번들 fingerprint에 연결된, 네이티브 재서명/설치용 실제 app payload를 복사하여 보존함. `.fileURL`에서 이 캐시를 참조.
4. `SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift`: 이미 DB에 등록된 앱 중 실제 resignedBundleIdentifier에 team ID가 포함되면 preferredBundleID를 그대로 사용. 따라서 원본 팀 접미사를 두 번 붙이지 않아야 함.

## 새 P73 실행 경로 (P72와 차이)

- `ScarletGuestHostManagedBootstrap` actor를 실제 SideStore worker 소스에 추가. XPC에서 중복 호출이 들어오면 단일 작업으로 병합.
- 앱 확장 실행 파일 경로에서 **실제 Scarlet 호스트 .app 경로**를 도출하고, 정확한 호스트 번들 ID + 내장 Apple 프로파일 유효기간 + 서명팀과 현재 선택팀의 일치 + SideStore 팀 인증서 OU 일치를 검사.
- P71 로그의 `no_managed_apps_for_selected_team`을 success로 속이지 않고, **원본 `CacheAppOperation.cachePayload(for:)`**로 설치된 signed host 앱 번들을 캐시한 다음 `InstalledApp`, `InstalledExtension`, `Team` 원본 CoreData 구조에 등록.
- 이미 동일 resignedBundleIdentifier의 record가 있다면 기존 관리 기록을 건드리지 않음. A와 다른 팀 B가 선택되면 A 호스트를 B로 자동 등록/재서명하지 않음.
- Cache 또는 DB 기록이 실패하면 명시적 `host_registration_failed`; 성공한 등록 이후에도 실제 갱신에는 기존 `AppManager.shared.backgroundRefresh` + RSD live 재검증을 요구하며 재설치 성공은 절대 추정하지 않음.

## 범위·수락 조건

- iPhone에서 **선택팀이 현재 설치된 호스트의 서명팀과 같을 때** `automatic_managed_apps_inspected`의 count가 0에서 1 이상으로 이동하고, 원본 SideStore refresh worker가 실제로 호출되는지 확인.
- 선택팀 B에서 host A를 타 팀으로 자동 등록하지 않을 것. 이미 관리중인 앱은 중복 기록하지 않을 것.
- 서명된 앱 번들 캐시가 SideStore App Group에서 정상 접근 가능한지 확인; 디스크 공간·권한 문제는 명시적으로 구분. 실제 iPhone 설치 readback은 여전히 별도.
- 다이내믹 아일랜드·상태 막대, SideInstaller certificate export 작업의 완료 여부는 이번 빌드와 별개의 미해결 문제.
