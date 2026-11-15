# P74 — 상단 시계/배터리 숨김의 독립적 원인과 실제 동작 변경

## 입력 증거 (사용자 제공 실기기 P71)

- Signed iPhone iOS 27.2 24B119, Scarlet Build 3.8.71, commit `aadd4ce2325b`, current session `e7091b0f`, 198 JSONL events.
- seq 82 (`sample_index=650`): `safe_top_pt=62`, `root_safe_top_pt=62`, `visible_unsafe_controls=8`, `first_unsafe_control_y=3`, `visible_unsafe_images=7`, `first_unsafe_image_y=13`, `depth_capped=true`. 첫 화면은 실제 심각한 영역 침범이므로 상태 막대 숨김이 타당함.
- seq 108~109: `guest_owner_layout_contract_retained`, `header_controls_before=8`, `header_controls_after=5`, `header_gate_pass=true`; 이어 `guest_fullscreen_header_verified/full_fbscene_and_native_header`. 전체 게스트 창 확대/축소/자르기 없이 **실제 네이티브 헤더 수정이 유지됐다는 구체적 기기 증거**.
- seq 111 (`sample_index=2600`): 5개 남은 컨트롤 모두 스크롤 내부, `first_unsafe_control_y=60`, `first_unsafe_image_y=60`, `safe_top_pt=62`, `root_safe_top_pt=62`, `unsafe_text_nodes=0`, `visible_unsafe_controls=5`, `depth_capped=true` (옛 측정기는 깊이24까지만 확인).
- seq 112/124: P51 상태 막대 정책은 초기 8개 심각 침범과 이후 5개 경계 2pt 침범을 동일한 `unsafe>0`으로 판정해 `native_icons_withheld_guest_collision`, `status_hidden=true`를 지속.
- 이 로그는 헤더 수정 이후 시계/배터리가 실제 기기에서 나타났다는 증거가 **아님**. 깊이24까지의 기존 측정에서 보이지 않는 별도 컨트롤이 존재할 가능성을 배제해야 함.

## 실제 차이: P51/P56/P65와 별개의 변경

| 기존 | P74 |
| --- | --- |
| P51: 어느 깊이에서든 `unsafe>0`이면 PID 레벨 전체 숨김. 650ms 기록을 2600ms 영구 계승. | 기존 P51을 그대로 우선 적용. 이후 **실제 헤더 보정이 유지됐을 때에만** 상태 막대 문자·아이콘 영역의 심각한 점유가 사라졌는지 별도 증명. |
| P56: 헤더 + 스크롤 보정 후 위험 컨트롤 **완전 0개**를 2회 관찰해야 숨김 해제. | 컨트롤 5개가 y60에만 남아도 62pt Safe Area의 실제 시계/배터리 영역과 겹치지는 않을 수 있음. 근접 오차와 심각한 침범을 구별. |
| P65: 인셋/오프셋 등 뷰 배치 조작 반복, 체감상 상단이 잘리는 회귀. | **어떤 UIView의 frame, inset, contentOffset, transform도 변경하지 않음.** 상태 막대 정책만 2중 엄격한 근거에 의해 변경. |

## P74 native 구현

- 게스트 `ScarletGuestIslandContentGuard.m.txt`: 이미 존재하는 클리핑 감지 함수로 UIWindow 전체 UIKit 뷰를 깊이56/최대2400개까지 순회. UIControl/접근성 버튼, UILabel/UITextField/UITextView/UIImageView를 구별하고, status glyph 실영역에 더 가까운 `visibleY<safeTop-9`를 **severe**, `visibleY<safeTop-2`는 **near**로 분류. 완전 탐색 여부를 기록. 깊이 또는 개수 초과는 `scan_complete=false`, 자동 해제 금지.
- 기존 650ms/2600ms 진단·수정 시퀀스는 변경하지 않고 헤더 수렴 후 2850ms, 3550ms에 **읽기 전용 검사 2회**. 실제 루트가 UIWindow 정상 수준/전경/세로 화면에 부착되고 safeTop이 40~130pt 내이며 루트 safeArea가 일치해야 수집.
- `ScarletFullscreenSceneStack.swift`: 원래 위험 경고가 있던 동일 PID에 대해 네이티브 헤더 실기기 retained 확인(`chromeHeaderProtectedPIDs`) + 완전한 56단계 검사 + 중증 침범 0 + near 컨트롤 존재 + near 시작이 `[safeTop-9, safeTop-2]` 범위일 때만 첫 검사 기록. 700ms 후 두 번째 검사도 만족할 때 P51 숨김 상태 해제 후 실제 `UIStatusBarManager.isStatusBarHidden` 재조회. 세부 게스트 이름/앱ID/화면텍스트는 기록되지 않음.
- 회전/다른 PID/불완전 탐색/헤더 취소/깊은 실제 침범이면 기존 보호막 유지. 일반 모드, guest remote scene, 앱 서명과 계정 인증·다중팀 등록은 변경하지 않음.

## 검증/수락 기준

1. 실제 P74 서명 iPhone 동일 게스트에서 `guest_post_header_statusband_probe` 2850·3550 모두 `scan_complete=true`, `near_controls>=1`, `severe_nodes=0`, `first_near_control_y` 53~60을 기록해야 아이콘을 다시 보이도록 허용.
2. 새 `resident_native_status_band_guard=two_complete_near_boundary_proofs_status_released` 이후 `resident_native_status_band_readback.status_hidden=false`가 되어야 코드 효과 확인. 실제 화면 캡처·버튼 터치까지 확인해야 **디자인 문제 해결**로 분류 가능.
3. 심한 침범·깊이 캡·전경 전환·다른 PID에서는 상태 막대 숨김을 유지; 게스트의 원래 렌더링/배치·실제 크기·색상은 변경 없음.
4. 계정 A/B·자동 갱신 P73의 실기기 재설치 성공은 이 시각 개선과 독립적으로 미검증 상태. CI 통과만으로 성공 표시 금지.
