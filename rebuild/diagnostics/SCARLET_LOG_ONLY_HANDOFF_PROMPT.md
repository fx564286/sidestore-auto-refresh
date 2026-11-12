# Scarlet Crystal — 로그 한 개로 이어서 수정하는 AI 전용 지침 (R6P10)

사용자가 Scarlet Crystal 진단 로그만 제공하면 이전 시도 전체를 우선 분석하고, 같은 조치의 반복을 차단하면서 새로운 독립적인 해결책을 실제 코드에 반영해야 한다.

## 0. 입력 및 판정 순서

1. 로그 상단 `SourceCommit`, OS, `CurrentSession`, `CurrentLaunchAt`, `LogScope`를 읽는다.
2. `CURRENT RUN` JSONL의 직접 관측값을 요약한다.
3. `REMEDIATION HISTORY` JSON의 **모든 entries**를 읽어 `mechanism` 및 수정 위치 `code_locations`로 중복을 찾는다. 특히 `source_verification=source_unavailable`인 이전 프로젝트 항목은 추정으로 채우지 않는다.
4. 아래의 중복 금지 및 사전검증을 충족하기 전에는 어떤 코드도 수정하지 않는다.
5. `AI HANDOFF PROMPT`와 이력 JSON `schema`가 현재 빌드 소스와 일치하는지 확인한다.

## 1. 재시도 판별 키

새 조치와 과거 entry를 `(problem, mechanism, file, function/hunk, old behavior, new behavior)` 단위로 대조한다. **변수 이름, 버전명, 호출 시점, 파일 위치만 바뀌었을 뿐 인과 메커니즘이 같으면 이미 해본 조치**로 분류한다.

이전에 사용된 메커니즘:
- 호스트/게스트 Safe Area, additionalSafeAreaInsets, FBScene의 safeAreaInsetsPortrait/safeAreaEdgeInsets/peripheryInsets.
- UIWindow/UIViewController 루트 및 statusBarFrame/statusBarHeight/avoidanceFrame 조정.
- 회전 프레임 재계산, 62→0→62 순간값 캐시, 지연 타이머, 원본 화면 비교.
- UIKit 게스트 윈도우/루트 컨트롤 좌표 검사 및 overlay hitTest/외부 터치 shield.
- 가상 창/화면 배율/창 위치/상주 Scene 스택, 최초 원격 콘텐츠 ready/reveal/foreground.
- NSBundle/CFBundle 정책 교체 비교, UIApplicationSceneManifest 유무 비교.
- R6P9 호스트 UIWindowScene 연결 후 LiveProcess XPC 시작 순서 이동.
이미 실행한 방법을 다른 이름으로 다시 적용할 수 없다. 예외는 새 로그가 **동일 방법의 실패 원인을 설명하는 구체적 새 증거**를 제공하고, 이전 코드와 다른 단일 원인에 대한 검증 실험이 가능한 경우뿐이다.

## 2. 모든 새 수정의 필수 기록 형식

`rebuild/diagnostics/scarlet_remediation_history.json`에 고유 `id`를 가진 entries 항목을 추가하거나, 기존 테스트 결과를 해당 entry에 갱신한다. **다음 필드를 누락할 수 없다.**

- `id`: 누적 고유 번호. 이력을 지우거나 재번호 매기지 않는다.
- `date`, `version`, `problem`, `mechanism`: 수정 날짜·빌드/기능·증상·인과 메커니즘.
- `hypothesis`: 무엇이 실제 원인이라고 보며 왜 새로운가.
- `code_locations`: **실제 저장소 상대경로**, 클래스/함수·메서드, diff의 정확한 줄 범위 (`@@ ... @@`), 변경 전 코드 (`before`), 변경 후 코드 (`after`), 원래 변경 커밋을 기록한다. 하나의 작업이 3개 파일을 바꾸면 3개 모두 쓴다. 포괄적인 “Safe Area 수정함” 같은 설명은 불합격.
- `generated_runtime_targets`: 통합 Python 스크립트가 빌드 시 upstream 엔진 소스를 자동 수정했다면, Git 추적 스크립트 위치와 별개로 **실제로 생성·패치되는 엔진 파일 경로, 함수·메서드, 변경 전과 변경 후 코드, 생성 함수**를 모두 기록한다. 소스 파일이 현재 Git 저장소에 직접 추적되지 않는다면 이를 명시하고, Git diff인 것처럼 표시하지 않는다.
- `source_revisions`: 실제 코드를 변경한 **40자리 Git SHA**, GitHub 커밋 링크, 제목. 별도의 CI/릴리스 커밋은 소스 변경으로 혼동하지 않는다.
- `action`: 어떤 함수를 왜 바꾸고 어떤 시점/수치를 제거·추가했는지 구체적 설명.
- `observation`: 테스트 전후 실기기·CI 수치와 원본 로그의 식별 가능한 비민감 이벤트.
- `status`, `device_verification`: 코드 변경/정적 테스트/네이티브 컴파일/실기기 화면·터치 확인/실패를 구별한다.
- `repeat_policy`: 무엇이 이미 검증되어 재시도 금지인지 구체화.
- `rollback_commit`: 언제나 안전하게 되돌릴 수 있는 이전 정상 기준 커밋.
- `source_verification`: `git_patch_observed` 또는 `source_unavailable`; 모르는 코드를 추측하지 않는다.

과거 소스가 없는 entry는 `code_locations=[]`와 `source_unavailable`로 남긴다. 출처가 확인된 경우에만 실제 diff로 보완한다.

## 3. 수정·빌드 절차

1. 새 실기기 로그의 **관측/미관측**을 구분한다. 예: 이벤트 `fullscreen_scene_xpc_started_after_host_attach`는 실행 순서만 검증한다. `host_owner_top_pt=-1→62`는 계층 준비 순서가 남아 있음을 뜻할 수 있으나 상단 UI가 해결됐다는 뜻은 아니다.
2. 이력의 동일 메커니즘 및 코드 위치를 인용해 제외하고, 비중복 가설 2~3개를 비교한 뒤 증거가 가장 강한 단일 후보만 수정한다.
3. 소스 diff를 만들어 코드 위치·변경 전후를 기록한 다음, 정적 회귀 테스트, iOS Xcode CI, IPA 릴리스 여부를 확인한다.
4. 기존 게스트 배율·회전·세션 A/B·PID 유지·원본 V48 버튼·Liquid Glass·인증서·페어링·번들 ID는 명시적 요청 없이 변경하지 않는다.
5. 같은 PR/브랜치에 **코드 diff와 이력 JSON 수정**을 함께 넣는다. 다음 빌드에서 진단 보고서에 완전한 JSON과 이 프롬프트가 포함됐는지 회귀 테스트한다.
6. 테스트 실패/원인 미확정도 이력에 남긴다. `Xcode archive success`는 `device_visual_and_touch_pass`와 다르다.
7. 사용자가 새로운 로그만 주면 앞서 확인된 사항을 재요구하지 않는다.

## 4. 직전 R6P9 실기기 사실

- iOS 27.2 build 24B119, 소스 `f29ddd833305`.
- XPC 실행 전 호스트 windowScene/parent 부착을 확인하는 `fullscreen_scene_xpc_started_after_host_attach` 이벤트는 실제 발생.
- PID 1120/1130 게스트 실행·원격 콘텐츠 부착·오디오 pause 성공 응답을 확인.
- 최초 `native_hosting_safearea_owner_readback`은 `-1`에서 시작해 `62`로 바뀜; 호스트 62→0→62 변화도 재발.
- R6P9 변경에도 **다이내믹 아일랜드 상단 가림 및 터치 정상화는 증명되지 않음**. 재차 XPC 실행 순서, Safe Area 캐시, UIKit 루트를 비슷하게 손보는 행위 금지.
- R6P8: 두 게스트 NSBundle/CFBundle 정책은 교체 후 일치. Scene manifest의 차이는 관찰됐지만 인과관계는 아직 입증되지 않음.

## 5. 출력 구조

**핵심 현상**: 현재 커밋/장치 관측과 화면·터치 해결 여부.

**이미 실패한 수정(재시도 제외)**: 이력 ID, 실제 파일+함수+before→after, 실기기 결과를 명시.

**새 독립 원인 가설**: 이전 방식과 달라지는 핵심 원인, 관측 가능한 반증 조건.

**실행 결과**: 변경 파일, 줄/함수, 코드 diff, 커밋, Xcode CI, IPA, 안전한 롤백 경로.

**이력 반영**: 새 entry ID와 수정된 JSON 및 앱 진단 보고서에 이력이 포함됐는지 확인.

로그에 정보가 없어 실기기 UI를 판단할 수 없다면 그대로 적고, 알 수 없는 문제를 이미 해결됐다고 주장하지 않는다.
