# P75 — 계정별 기기 설치 앱 관리 권한 분리

## 관찰과 독립성
- P71(서명 iPhone 3.8.71) `settings_account_switch_verified`는 네 차례 기록됐으나, 팀별 `listManagedSlots` 및 `setManagedSlot` 실행 성공 여부는 기록되지 않았다.
- P68은 원본 SideStore IPA install 및 refresh에만 선택한 Apple Team ID·인증서 OU 제약을 적용했다.
- P61 `ScarletDeviceInstallAgent.swift.txt`의 슬롯 관리 코드에는 `InstalledApp.all(in: context)` 전체를 바로 반환하고, 앱 번들 ID만으로 활성화/비활성화하는 별도 로직이 남아 있었다. 계정 A가 활성화된 상태에서 B 소유 앱 정보가 노출되거나 B 앱에 AppManager 호출이 들어갈 가능성이 있었다.

## P75 변경 (P68/P73/P74와 별개)
- `listManagedSlots`: 기존 SideStore 계정/설치/갱신과 동일한 `ScarletTeamOperationGate`를 선점한 뒤 실제 인증된 Apple Team을 확인하고, `InstalledApp.team.identifier == selectedTeamID`인 항목만 표시. 실패하면 목록을 반환하지 않음.
- `setManagedSlot`: 기존 `ScarletSlotOperationGate` + `ScarletTeamOperationGate` 양쪽을 점유해 계정 전환 경쟁을 차단. bundleID로 찾은 원본 `InstalledApp`의 team을 현재 인증 Team과 반드시 비교하며 불일치 시 `selected_team_app_mismatch`로 중단. 그 후에만 기존 호스트 보호와 SideStore 활성화/비활성화 호출 실행.
- 실제 원본 P61 `AppManager.shared.activate/deactivate`·사전 확인·데이터 백업 경로 유지; 게스트 화면/크기/다이나믹 아일랜드 및 사용자 UI 색상은 변경하지 않음.

## 수락 기준
1. Apple ID A로 전환 → 기기 설치 앱 관리에서 Team A 앱만 노출, Team B 앱 행 없음.
2. B의 bundleID를 변조해 A 상태에서 `setManagedSlot` 호출 → `selected_team_app_mismatch`, AppManager 호출과 데이터 변경 0건.
3. B 계정 전환 후 Team B 앱만 표시되며 실제 Team B 인증서로 조작. 동시 A↔B 전환은 선점 게이트에서 거부.
4. 원래 Scarlet 호스트·SideStore는 선택팀과 무관하게 비활성화/제거 금지.
5. 모든 권한 통과와 원본 백업/복원 실제 동작은 서명한 iPhone 실기기에서 추가 확인할 것. 로컬 Python·CI는 코드 및 빌드 검증만 입증.
6. P74의 상단 status-band 복구는 P71 후속 소스 변경이며 사용자 기기에서 아직 검증되지 않음. 상단 실물 시각 문제를 해결했다고 보고하지 말 것.
