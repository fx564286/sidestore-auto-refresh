# Scarlet Crystal V155 — 단일 LiveProcess 실행 경로

## 설계 결정
이전 V154(3.8.227)에서 사용자에게 문제가 있던 Direct 실행 경로를 **게스트 실행 경로에서 제거**한다.
사용자 게스트 앱은 LiveProcess를 통해서만 실행한다. 기존 Apple ID, App ID,
SideStore, 저장된 게스트 앱 파일, 컨테이너 데이터, JIT 설정, 인증서는 삭제하거나 변경하지 않는다.

## 변경 영역
- `LCAppModel.runApp`: `classicMode` 플래그/명시적 `multitask=false` 요청과 무관하게 LiveProcess를 사용. 이전 설정값은 저장된 그대로 보존. LiveProcess 시작에 실패하면 오류를 반환하고 Direct로 우회하지 않음
- 앱 목록의 Classic/Multitask 이중 실행 메뉴 옵션 제거
- `LCBootstrap.m`: `SCGuestMorphPresenter`, Direct 전용 `UIWindow` 및 버튼, objc_msgSend 링크를 소스에서 삭제. 유효한 LiveProcess/SideStore가 아닌 게스트 부트스트랩 시 명확한 오류
- `V3UnifiedShell.dispatchURL`: Direct 호스트 복귀 전용 URL 콜백 삭제; 일반 설치·SideStore 링크는 유지
- `MultitaskDockView`: Direct 재시작 버튼/분기/ObjC 브리지 삭제. 정상 상단 두 탭과 창 관리 액션은 유지
- 최근 앱 Optical Glass 행 내부 상하 6pt 마진을 고정 스크롤 높이에 반영(+12pt)
- 기존 투명 배경 오버레이에서 패널 외 영역만 명시적으로 hit-test 처리

## 예상되는 제한
- LiveProcess extension, 권한, iOS 지원이 필요한 게스트는 실패 시 오류 메시지 표시. 이전 Direct 실행으로 **자동 전환하지 않음**.
- 특정 앱이 LiveProcess를 지원하지 않는 경우 앱 기능 호환성이 떨어질 수 있으므로 설치 후 테스트 필요.
- SideStore 본체의 인증/서명/새로 고침 로직은 이 정책과 별개로 유지.

## 검증
- 소스 불변성·단일 경로·이중 UI 제거·컴파일 바이너리 marker 정책·앱 데이터 미삭제 검증
- V154와 V155의 Source audit는 버전별로 분리. 이전 V154 바이너리 감사 규칙은 유지.
- GitHub Actions에서 Fast Preflight → 전체 Xcode/IPA 아카이브 실행.
- 실제 아이폰에서 최근 앱 롱터치 잘림, 바깥을 눌러 닫기, LiveProcess 전환 정상 여부는 별도 점검.
