# Scarlet Crystal — Figma / Liquid Glass / 기능 검증·모니터링

현재 개발 기준: `rebuild/scarlet-from-zero-20261106` / PR #46.
Figma 원본: https://www.figma.com/design/QESg6S7oJS47PmlPpEX5w5

## 정확하게 확인 가능한 범위

| 단계 | 측정·증거 | 자동 감시 여부 | 제한 |
| --- | --- | --- | --- |
| Figma 원본 텍스트·구조 | 직접 읽은 6개 화면 ID와 라벨/크기 `rebuild/design/figma-measured-baseline.json` | 코드가 바뀔 때 테스트 | Figma 파일이 바뀌면 기준 재추출 필요 |
| SwiftUI 소스 대응 | `test_measured_figma_parity.py` 외 UI 계약 테스트 | GitHub Actions push/PR | 텍스트·구조만, 화면 픽셀 보증 아님 |
| SwiftUI 실제 렌더링 | iPhone Simulator PNG 5종 + `metadata.json` | GitHub Actions 시뮬레이터 작업 | **모의 탭바/버튼** 사용. Native Glass 증거 아님 |
| Liquid Glass 원본 광학 효과·터치 | 실제 `UIGlassEffect` 호스트 연결 소스, 제스처 로그, 명암 다른 실기기 영상 | 호스트 미연결 = BLOCKED | 현 신규 프로젝트는 원본 UIKit 호스트 구현 없음 |
| 로컬/서비스 버튼 기능 | `ScarletControlAuditTrail`의 결과 코드를 기록 | 코어 테스트만 자동; 기기 연결 전 앱 로그 불가 | 보안상 암호·2FA·토큰 출력 없음 |
| 로그인/페어링/설치 | 실제 기기 서명 프로파일·App Group·설치 성공 확인 | 현재 기기 측 수집 미구현 | CI는 사용자 iPhone에 자동 접근하지 못함 |
| 무료 7일 갱신 | 프로파일 만료·재설치 결과 검증 정책 | 정책 테스트 및 기존 별도 만료 감시 | 유효기간 제한 자체 제거 불가 |

## CI 확인

GitHub Actions: https://github.com/fx564286/sidestore-auto-refresh/actions/workflows/scarlet-clean-core.yml

아티팩트 두 종류:
- `Scarlet-Clean-UI-Figma-Parity-Simulator-Only`: `home.png`, `apps.png`, `sources.png`, `settings.png`, `connection.png`. **모의 Liquid Glass**라고 메타데이터에 표시.
- `Scarlet-Clean-Release-Readiness-JSON`: 누락된 원본 Glass/호스트/실기기/설치 증거를 개별 차단 항목으로 보고.

개발 소스 체크 통과는 **릴리스 준비 완료가 아님**. `rebuild/scripts/audit_readiness.py --enforce-release`는 필수 실기기 근거가 없으면 실패하도록 설계했다.

## Native Glass 실기기 합격 조건

1. 하단 `Home / Apps / Sources / Settings` 네 탭에 **기존** UIKit/SwiftUI 원본 Liquid Glass 소재를 사용하고, 선택 변화·상호작용이 정상 동작.
2. 둥근 앱 전환 버튼이 1개이며, 터치와 롱터치가 기존 최근 앱·창 관리 패널로 연결; 버튼에 다른 계층이 터치 가로채지 않음.
3. 최근 앱과 창 관리 패널 크기/간격 동일. 최소화·최대화·닫기 버튼은 길게 눌러도 잘리지 않음. 바깥 부분 최초 터치에 닫힘.
4. 밝고 어두운 게스트 배경에서 반사/굴절·투명도를 영상/이미지로 확인. 단순 `.ultraThinMaterial`이나 Figma의 배경 블러를 **Liquid Glass 검증으로 인정하지 않음**.
5. 세로↔가로 회전 후 상단 터치 영역과 영상 여백이 손상되지 않고 패널 크기가 유지되며, 44pt 이상 타깃과 VoiceOver, Dynamic Type 확인.

## 버튼별 로그 설계

새 Swift 코어에 `ScarletControlAuditTrail`을 추가했다. 이벤트는 `time, action, state, problem` 네 값만 수집하며 최대 200건 메모리에 유지. 사용자 계정, 토큰, 2FA 코드, UDID, 임의 예외 문자열은 기록하지 않는다.

이는 아직 실기기 앱의 호스트에서 주입되지 않았으므로 **아이폰 기능 로그 모니터링 성공을 뜻하지 않는다**. LiveContainer/SideStore 호스트가 연결될 때 해당 actor를 `ScarletActionCoordinator`에 전달하고 설정 → 진단 로그에서 내보내기/확인할 수 있도록 구현해야 한다.

## 남아 있는 차단

- 새 SwiftUI UI가 실제 LiveContainer 호스트의 런처와 연결되지 않음.
- 원본 `UIGlassEffect` 렌더러가 새 호스트에 포함·검증되지 않음.
- Figma 창 관리 패널에 대응하는 호스트 기반 창 제어 실제 동작 없음.
- SideStore/SideSign 로그인, 2FA, 기기 서명, 재설치 결과 검증 없음.
- 신규 설치 가능 IPA 없음.

기존 사용자 앱 데이터와 번들 `com.kdt.livecontainer.P8EZT3U5N4`은 유지 대상으로 지정; 테스트 과정에서 삭제하지 않는다.
