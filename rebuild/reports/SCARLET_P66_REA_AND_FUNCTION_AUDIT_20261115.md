# Scarlet Crystal · P66 REA 및 기능 차단 해소 감사

검사 대상: P65 commit `f6f72ae29c84`의 현재 사용자 로그(2026-11-14 23:36:55 UTC)와 첨부된 SideInstaller/LCSign IPA.
목표: 화면에만 존재하고 실제 실행을 차단하던 기능을 실사용 엔진에 연결하며 기존 V48 호스트, 인증서, 게스트 데이터를 보호.

## 입력 IPA 정적 검사
| 항목 | SideInstaller | LCSign |
| --- | --- | --- |
| 버전 | 2.0.1 (1) | 1.4 (7) |
| Bundle ID | com.frizzlem.sideinstaller | com.huami.LoadController |
| 바이트 | 10,770,716 | 22,882,152 |
| SHA-256 | 7637cdf901bfd7d8c553530065852c8d1cca5019a706709227ab7ec673cfadc0 | ac438289b0054dfea1a435d7128f4649c07b92abd89b560432ebc1913d6ad8b5 |
| IPA CRC 검증 | 통과 | 통과 |
| 실행 파일 식별 | AccountStore, SavedAccount, AccountEditor, PairingManager, SideStorePairingHandoff, ProvisioningProfile, InstallProgressBar | CertificateStore, IPAInstaller, IPASignerError, BackupRestoreView, QuickInstallBatchPreviewView, SigningCertificateCard |

Binary/source separation: 해당 IPA는 비공개 빌드 결과물로, 문자열·Info.plist·클래스명 관측만으로 메서드 내부 동작이나 iPhone 설치 성공을 증명하지 않는다. 제3자 바이너리, 비밀키, 앱 아이덴티티는 Scarlet에 복사하지 않았다.

## 차단 상태와 실제 코드 연결

1. **P65 추가 로그인**: `apply_scarlet_host.py`의 버튼은 안내창만 띄우고 `ScarletAppleIDLoginSheet`로 이동하지 않음. **P66** 버튼을 실제 시트에 연결, 두 번째 ID 편집, 2FA, 세션 검증 및 계정 목록 전환 구현.
2. **SideStore 원본 단일 인증 토큰**: `AuthManager`의 인증 정보는 1개 세트. **P66** 계정별 비밀을 iOS Keychain으로 별도 저장하고, 선택 시 원래 AuthManager 활성 슬롯과 CoreData 활성 팀만 전환. 실패하면 이전 보존 세션 복원.
3. **개발팀 하드코딩**: P65 원본 `ensureActiveTeamForRefresh`가 다른 Apple ID 팀을 무조건 P8EZT3U5N4와 대조. **P66** 신규 계정 로그인에서는 Apple Developer Portal이 실제 반환한 팀을 허용, 호스트 재설치·갱신에서는 기존 서명 팀 요건을 그대로 강제.
4. **앱 설치 슬롯**: P61은 SideStore CoreData 기반 활성화/비활성화 수단을 구현, 실제 기기 복구 검증은 없음. P66은 해당 구현을 유지하며 기기 설치를 추정 성공으로 바꾸지 않음.
5. **수동 앱 갱신**: `ScarletSigningReadinessPanel.swift`에 원본 SideStore worker로 연결된 `지금 갱신` 버튼이 이미 존재. 별도 레거시 `serviceRefreshApp` 분기에는 `transport_unverified` 차단 메시지가 있으나, 현재 독립 홈 UI에서 이 분기를 호출하지 않음. 사용자를 속이는 비활성 기능이 추가 노출되지 않도록 기존 수동 갱신 경로 유지.
6. **게스트 상단 및 상태표시줄**: P65 장치 로그의 시계·배터리 은폐 및 잔여 위험 컨트롤은 미해결. P66은 인증 경로만 수정, 앞선 V48 geometry 실험을 반복하지 않음. 다음 P65/P66 실기기 로그에서 별도로 판정.

## 수락 기준 및 증거 경계

- 추가 로그인: ID A → B 인증 → A 전환 → 앱 재진입 및 A/B 상태 유지, iPhone에서 2FA 및 개발팀 확인.
- 인증서 및 설치: 새 계정 선택과 원래 Scarlet 호스트의 팀/서명 검증은 서로 다른 조건. **로그인 성공만으로 앱 설치 성공 처리 금지**.
- 원복: 계정 B 인증/팀 저장 실패 시 계정 A 활성 토큰/팀 복원. 인증서, 게스트 앱, 기존 페어링 삭제 금지.
- 정적 회귀: P66 744 Python 테스트 실행, 741 통과/3 환경상 skip. 실제 Xcode27.2 native CI 및 iPhone 서명/설치/계정 전환은 별도 확인 필요.

## 새로운 소스 접근 방식
기존 인증 과정을 단지 안내문이나 로그로 수정한 것이 아니라, 실제 XPC worker→Keychain→CoreData→SwiftUI 경로를 추가했다. 본 구현이 영향을 주는 파일과 불확실성을 L114 변경 이력에 기록한다.
