# P83 / L138 — 상단바 중복 표시 정책 소유권 수정

## P81 실제 기기 증거 (Source c5ad675 / session e5f30ba9)

- PID553: 650ms `visible_unsafe_controls=9`/safeTop62; 2600ms 0; 2850ms severity0; 3550ms 심각 충돌 2개, nearControlY50. `status_hidden=true`가 유지되어 시계/배터리가 사라지는 근본 현상 남음.
- PID649: native initial `unsafe_controls=0`이지만 2850ms/3550ms severe_nodes=1(상단 이미지); statusbar `status_hidden=false`.
- seq125 overlay `overlay_is_key=true` while `status_hidden=true`. The floating UIKit overlay can become key while the host SwiftUI root and child independently publish identical `.statusBarHidden` and overlay UIKit `prefersStatusBarHidden=false`.

## P83에서 실제 변경한 코드

1. `ScarletIntegratedHostView.swift`: 뷰포트 child `.statusBarHidden` 삭제. host root `.statusBarHidden(fullscreenStack.isVisible && nativeStatusBarCollisionShield)`만 유지.
2. `ScarletFullscreenGuestTab.swift`: floating UIWindow UIKit owner가 무조건 `false`를 표시하지 않고 host 위험 상태 `residentBarHidden`을 따라가도록 변경. `syncResidentStatusBarHidden`는 표시 중이고 현재 Scene에 연결된 resident floating owner만 건드림. V48 original pan 및 애니메이션/터치 경로는 그대로.
3. `ScarletFullscreenSceneStack.swift`: PID 경고, 검증된 안전 해제, 게스트 A/B 전환, 게스트 톤 갱신 시 동일 정책을 overlay owner에게 전달. 상태바를 무조건 숨기거나 보이게 하지 않음.
4. 이전 P47/P51 테스트의 낡은 정적 기대치를 수정하고 P83 전용 회귀 테스트 추가. CI 버전 3.8.83, 기존 번들 식별자 보존.

**검증**: 로컬 전체 820 테스트 OK (3 infra skips), 중복 수정 gate P83 proposal 통과. Xcode27.2 네이티브 컴파일/IPA/실기기 결과 별도 확인 필요.

**미해결 / 다음 조치**: P81 유효한 게스트 내부 safeTop62에도 3550ms에 y50 상단 요소가 다시 등장함. 본 조치는 상태바 표시 '정책 소유권'에 한정되어, 그 내용을 safe guide 아래로 재배치하는 별도 네이티브 레이아웃 해결이 필요. 컨테이너 전체 크기 변경, 절단, 임의 안전 영역 62pt 추가, 상태바 강제 은폐로 해결을 주장하면 안 됨.

**P83 source commit**: `40e7e8c03dd25ff9afaa1c5dcdc1d6fdde45f699`; **branch**: `fix/scarlet-v48-r6p83-single-statusbar-authority-20261116`.

## L139 / 동일 P83 릴리스 게시 조건 결함

- GitHub Actions run `43806370645`: `livecontainer`, `sidestore`, `package-paired` 모두 success. `publish-unsigned-github-release`는 skipped.
- 원인: `publish-unsigned-github-release.if`가 P81까지만 포함. P83 브랜치가 빠져 자동 게시 작업이 실행되지 않음.
- P83 브랜치만 기존 허용 목록에 추가. 기존 3.8.83 IPA, 4개 확장, 동작, 인증서, 서명 경로 변경 없음.
- 정적/회귀 테스트 **822개, 3 infra skips, 실패 0**. 릴리스의 공개 URL은 asset 실제 존재 확인 후 제공해야 함.
- P81 게스트 상단 배치 문제와 L139 배포조건은 완전히 독립적임.
