# Scarlet Crystal P72 — 샘플 IPA·P69 pairing race 실행 경로 대조

## 직접 확인한 파일 (2026-11-15)

| 대상 | 버전 | Bundle ID | UIKit scene / 상단바 관측 |
| --- | --- | --- | --- |
| 사용자 제공 SideInstaller.ipa | 2.0.1 (1) | `com.frizzlem.sideinstaller` | `UIApplicationSceneManifest` 없음; `UIStatusBarHidden` 없음 |
| 사용자 제공 LCSign-1.4-7.ipa | 1.4 (7) | `com.huami.LoadController` | 단일 `LCSceneDelegate`, `UIApplicationSupportsMultipleScenes=false`; `UIStatusBarHidden` 없음 |
| 실제 P71 공개 IPA | 3.8.11 (3.8.71) | `com.kdt.livecontainer.P8EZT3U5N4` | `UIApplicationSupportsMultipleScenes=true`, 원격 LiveProcess 게스트, `UIStatusBarHidden` 없음. SwiftUI의 조건부 `.statusBarHidden`은 런타임 정책 별도. |

세 파일의 ZIP CRC 검사에 오류 없음. SHA256: SideInstaller `7637cdf901bfd7d8c553530065852c8d1cca5019a706709227ab7ec673cfadc0`; LCSign `ac438289b0054dfea1a435d7128f4649c07b92abd89b560432ebc1913d6ad8b5`; P71 `4c95a2f3bb0faa869dcc8dddc2e08f3ed0b03788bfe940121683409066630145`.

샘플 IPA의 키·내부 메서드 동작을 이 정적 확인만으로 복원하거나 정상 설치를 입증할 수 없음. UI 외관이 같다는 이유로 `UIRequiresFullScreen`이나 scene manifest를 Scarlet에 복사하지 않음. 특히 LCSign의 single scene 구조는 Scarlet의 resident LiveProcess 장면 아키텍처와 다른 설계임.

## P69→P71→P72 pairing causality

- P69 실제 iPhone `pairing_restored` 이후 독립 XPC `pairing_state_read_timeout`이 20초 후 발생. 이는 기기 자체의 페어링 취소 입증이 아니라 **호스트 preflight 응답 부재**.
- P71: 30초 동안 성공한 XPC 검사 결과를 메모리에서 재사용하고 동시 preflight 병합. 이후 30초 경과나 최초 검사 timeout에는 여전히 `guard paired else`가 native 갱신을 **실행 전에 차단**함.
- P72: `pairing_state_read_timeout` 한 가지 불확실 응답만 통과시켜 원본 `ScarletNativeRefreshInspector.inspect()`와 실제 `ScarletNativeRefreshExecutor.execute()`를 시도함. **실제 SideStore worker의 post-sign `ensurePostSignInstallTransport()`가 RP record, tunnel, live UDID를 다시 검증**하므로 무검증 설치 허용이 아님. `pairing_file_missing`, `pairing_invalid`, `pairing_protocol_mismatch`, `transport_unavailable` 등 명시적 실패는 여전히 차단.
- `automatic_pairing_preflight_inconclusive` 로그는 `installation_verified=false`를 명시; 실제 재설치/프로파일 변경은 별도 확인.

## 별개로 미해결인 화면 문제

`ScarletIntegratedHostView.swift`의 `.statusBarHidden(fullscreenStack.isVisible && fullscreenStack.nativeStatusBarCollisionShield)`가 native 시계/배터리를 숨김. 충돌 정책은 650/2600ms 위험 컨트롤 감지에 따라 래치되므로 게스트 레이아웃을 바로잡지 못하면 아이콘을 숨긴 상태가 지속. `.statusBarHidden(false)`로 우회하면 겹침이 재발할 수 있어 P72에서 변경하지 않음. 이미 시도한 게스트 safe area / header frame / nested scroll / viewport 변형을 반복하지 않음. 실기기 화면·터치 수락은 미확인.

## 검증 기준

P72 native CI 및 실제 서명 iPhone에서 계정 A/B 선택·갱신·페어링 경로를 확인하고, 원본 SideStore worker 실패를 `pairing_state_read_timeout` preflight 오류와 분리해야 함. IPA 서명/설치 및 계정별 팀 인증서와 Dynamic Island 시각/터치 검증은 CI 통과만으로 완료 처리하지 않음.
