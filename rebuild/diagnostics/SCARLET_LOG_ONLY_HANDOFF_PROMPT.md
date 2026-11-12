# Scarlet Crystal — 로그 한 개로 이어서 수정하는 AI 전용 지침 (R6P13)

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


## 6. 자동 중복 차단 게이트 (R6P13)

이 보고서는 단순 런타임 로그가 아니라 다음 코드 변경을 결정하는 **보존된 실패 실험 기록**이다.

- 보고서 앞부분 \`NO-REPEAT DECISION INDEX\`는 최근 수정 ID/버전/원인 메커니즘/상태/코드 파일을 먼저 보여준다. 전체 변경 전후 원본 코드와 커밋은 뒤의 \`REMEDIATION HISTORY\`에 보존된다. 앞부분만 보고 이전 이력이 없다고 판단하지 않는다.
- 수정 **전에** 후보 작업을 JSON으로 작성해 \`python3 rebuild/diagnostics/scarlet_no_repeat_gate.py --proposal proposal.json\`을 실행한다. 실패하면 코드 수정을 시작하지 않는다.
- \`novelty.prior_excluded_ids\`, \`novelty.causal_difference\`, \`novelty.falsifiable_prediction\`은 필수다. 동일 실패 원인을 다시 사용할 경우 실제 기기에서 얻은 \`source_commit/event/observed_value\`와 이전 방식이 실패한 구체적 이유까지 제출해야 한다.
- 소스의 변경 전후가 기존 이력과 실질적으로 같은 경우, 메커니즘 이름이나 버전만 바꿔도 \`NO-REPEAT-BLOCK\`으로 거부한다. 빈 전후 코드·diff hunk가 없는 새 조치도 거부한다.
- CI 테스트가 같은 검증 함수를 호출하여 **빌드 시작 전** 이력을 검사한다. 프로그램이 인과관계의 모든 동의어를 자동 이해한다고 가정하지 않는다. 의미적으로 유사한 조치는 앞의 \`재시도 판별 키\`에 따라 추가로 수동/AI 검토해야 한다.
- 새 작업이 성공하지 못한 경우에도 실패 사실과 수정 코드 범위를 \`Lxxx\`에 남긴다. 새 로그를 받으면 이전 실패 메커니즘은 자동 제외 후보이며, 성공으로 바꾸려면 별도 실기기 시각·터치 증거가 필요하다.

### 최신 기기 관측: R6P11 SDK 실험 (2026-11-12)

\`SourceCommit=687fb754e837\` 실기기 보고서에는 PID 2318과 2334에 각각 \`resident_sdk_contract_selected\`, \`sdk_source=user_override\`, \`result=dyld_sdk_query_requested\`가 기록됐다. 따라서 두 게스트에 R6P11의 **자동 Mach-O SDK 선택 분기**(\`effectiveSDK == 0\`)가 실행됐다고 주장할 수 없다. 이 이벤트는 API 변경 요청을 뜻할 뿐 UIKit 상단 콘텐츠가 물리적 Dynamic Island 아래에서 벗어났음을 입증하지 않는다. 기존 Safe Area/Scene/상단 좌표 조정과 R6P9 부팅 순서 변경을 새 이름으로 재시도하지 않는다.

## 7. R6P15 이후 정확한 이력 보존과 새 코드 변경 검증 (R6P16)

현재 설치된 R6P15 보고서의 `SourceCommit=a3eedc4174c9`는 실제 GitHub R6P15 HEAD다.
따라서 **현재 버전은 R6P15**이며, 기존 51개 항목 L001~L051 중
L049=R6P14 스위처 이동·즉시 접기, L050=R6P15 게스트 자체 루트 Safe Area,
L051=R6P15 저장된 RSD 연결의 제한적 재검사다. 과거 항목에 `device_visual_and_touch_pass`가 없으면
완성된 화면 수정으로 간주하지 않는다.

### 이번 실기기 로그에서 판정된 항목

- R6P14 `switch_panel_navigation_reset(reason=go_home/enqueue_guest)`를 실제 관찰했다.
  A를 나와 B를 실행해 count=2인 것도 관찰했다. 그러나 패널의 모든 픽셀 및 전환 속도는 로그만으로 확정할 수 없다.
- R6P15 실행 시 `safe_top_pt=0` 순간값이 계속 나타났고, `guest_safe_top_pt=62`,
  `native_hosting_safearea_owner_readback(host_owner_top_pt=-1 -> 62)`를 관찰했다.
  게스트 내부 실제 루트에서 `guest_root_corrected`와 사용자 터치 검증은 보이지 않는다.
  기존의 FBScene/루트 additionalSafeAreaInsets/시간 지연 방식 재적용을 금지한다.
- `resident_sdk_contract_selected(sdk_source=user_override)`는 R6P11 실험이 자동 SDK 선정으로
  입증됐다는 뜻이 아니다.
- 별개의 미해결 사항: IPA 설치의 `appmanager_error_code_3`; 수동 갱신은
  `installation_verified=false`. 이 둘을 성공이라고 보고하면 안 된다.

### R6P16 빌드 차단 계약

1. P15까지의 L001~L051 원본 기록은 내용 해시로 고정된다. 이전 실패를 성공으로
   재기록하거나 원본을 지우는 대신 L052, L053… 항목을 **추가**한다.
2. R6P15 기준 Git 커밋 `a3eedc4174c9db698065ecfee7c7da6a9ac316b8` 이후
   `rebuild/HostApp`, `rebuild/Sources`, `rebuild/integration`, `rebuild/Tests`,
   `rebuild/diagnostics`, `rebuild/scripts`, 해당 CI workflow의 모든 변경 커밋과 파일을
   새 이력의 **정확한 SHA 및 코드 경로**와 일대일로 대조한다.
3. `python3 rebuild/diagnostics/scarlet_no_repeat_gate.py --repository-check`에서
   `[NO-REPEAT-BLOCK] UNRECORDED SOURCE COMMIT ...`가 발생하면 Xcode/IPA 단계 전에
   빌드가 실패해야 한다. CI는 `fetch-depth: 0`으로 전체 커밋을 검사한다.
4. 새 수정 전에 `--proposal`도 제출하여 같은 원인과 변경 전후 코드를 먼저 비교한다.
   P15 게스트 자체 루트 Safe Area 조치를 `safe_area`와 별개라고 명명하는 우회도
   중복 분류에 포함한다. 미검증 조치는 별도 원인·실제 기기 증거가 없으면 차단한다.
5. 보고서 첫머리에는 최근 18개가 아닌 **전체 수정 ID와 상태·파일을 표시**한다.
   각 entry의 원본 코드 전후 및 작업 당시 정확한 커밋은 뒤의 원본 JSON에 있다.
   반드시 `SourceCommit`과 `entries[-1]`을 비교하여 설치 기기 버전과 개발 이력을
   혼동하지 않는다. 실제 CI에서 후속 버전이 배포되더라도 이전 기기 로그는 여전히 P15다.
6. 새 수정에 대한 표준 수용 조건은 **이력 등록+동일 SHA/파일 대조 통과+테스트+네이티브
   빌드+실기기 확인**이며, 단계별 상태를 따로 기입한다. `source_committed_ci_pending`을
   해결 완료라고 바꿔서는 안 된다.

## 8. R6P17: P15 보정기 비활성화의 독립 원인 — 원본 LC UserDefaults와 게스트 전용 UserDefaults

- 2026-11-12 05:04:21 UTC R6P16 실기기 로그 `SourceCommit=c17b16519c2b`는
  52건 L001~L052의 전체 내역, 게스트 2개 실행과 패널 즉시 접기를 확인하지만,
  `guest_root_safearea_receipt`를 **한 번도** 포함하지 않는다. 따라서 Safe Area가
  62pt라는 호스트 기록을 R6P15의 실제 게스트 루트 보정 성공으로 해석할 수 없다.
- 고정된 upstream LiveContainer 커밋 `9108ae624ea001f7d7696d48407f890b48fa2653`의
  `LiveProcess/main.m`에서 `NSUserDefaults.standardUserDefaults`(초기 원본 LC 저장소)에
  `Scarlet.ResidentSDKContract.V1`을 기록한다. 그런데 그 뒤 `LCBootstrap.m`의
  `NUDGuestHooksInit()`가 `Tweaks/NSUserDefaults.m`에서
  `NSUserDefaults.standardUserDefaults = newStandardUserDefaults;`로 **게스트 저장소 교체**를 수행한다.
  R6P15 `ScarletGuestIslandContentGuard.m`은 교체된 `standardUserDefaults`를 읽어
  원본 LC가 기록한 플래그를 찾지 못하면 조용히 종료할 수 있다. 이 메커니즘은 이전
  Safe Area/FBScene/호스트 프레임 수정과 무관한 **시작 조건·저장소 동일성** 결함이다.
- R6P17은 이미 보존된 `NSUserDefaults.lcUserDefaults`를 조회하도록
  **읽는 객체만** 교체한다. 나머지 화면 배율, 상단 여백 공식, root.additionalSafeAreaInsets,
  다이나믹 아일랜드 회피값, 버튼, 멀티탭, 페어링, 인증서는 변경하지 않는다.
- 보정기 시작 성공 시 `guest_root_safearea_receipt(result=guest_root_guard_armed)`가
  게스트 프로세스 PID별로 우선 기록되어야 한다. 이후 `guest_root_already_safe`,
  `guest_root_corrected`, `guest_root_update_unconfirmed` 등으로 구체적 결과를 분리한다.
  시작 이벤트만으로 화면 겹침이 해결됐다고 판정할 수는 없다.
- 새 로그에서 `guest_root_guard_armed` 없이 SDK 선택 로그만 반복된다면
  P17도 실패 상태로 보고 주입·빌드 연계 또는 알림 수신 경로를 별개로 조사한다.
  `guard_armed`가 발생하지만 상단이 여전히 가려지면 Safe Area 값을 더 더하는
  대신 실제 화면 콘텐츠와 Safe Area 무시 여부를 검증한다. 다른 앱도 동일 기준으로 검사한다.
- 별도로 `appmanager_error_code_3`, 소스 IPA 다운로드의 `NSURLErrorDomain -999`,
  갱신의 `installation_verified=false`는 이번 상단 문제와 독립된 미해결 결함이다.
  R6P17 수정에 설치 성공/페어링 성공을 귀속시키지 않는다.

## 9. R6P17 실기기 반증과 R6P18 하위 콘텐츠 좌표 진단

- 사용자 제출 R6P17 보고서: `SourceCommit=9ea728fa80fd`, 세션
  `f7e99195`, iOS 27.2/24B119, 2026-11-12 05:30:00 UTC.
- PID `4585`, `4593`에 `guest_root_guard_armed`가 각각 1회, 이어
  `guest_root_already_safe`가 합계 7회 발생했다. 양쪽 모두
  `target=62`, `before=62`, `after=62`; **루트 Safe Area는 이미 정상이었다.**
  `guest_root_corrected`는 0회. 이 결과는 R6P17 원본 LC Defaults 플래그
  수정으로 보정기가 활성화됐다는 것을 증명하지만 상단 버튼 시각·터치
  해결을 증명하지 않는다. 기존 `additionalSafeAreaInsets`를 다시 더하거나
  FBScene/윈도 프레임을 조정하는 반복 수정은 금지한다.
- 첫 게스트 뒤 두 번째 실행 `recent_session_registered(count=2)`와
  `switch_panel_navigation_reset(go_home/enqueue_guest)` 관찰. 상태 유지.
- 별개의 소스 다운로드 실패 `NSURLErrorDomain -1005`(연결 손실).
  이 오류는 P16의 `-999`(취소)와 다르며, 자동갱신도 여전히
  `installation_verified=false`다. 상단 레이아웃과 별도 추적한다.
- 새 인과 가설: **루트 Safe Area의 62pt는 실제 하위 컨트롤이 62pt
  아래에 배치됐다는 증거가 아니다.** 원본 UIKit에서도 각 UIView의
  제약 조건과 개별 Safe Area 반영 여부는 다르다. 따라서 R6P18은
  게스트 프로세스 내부의 현재 UIKit UIWindow에서 실제 하위 UIView 중
  버튼/조작 요소 후보와 UIScrollView의 윈도 좌표를 **읽기 전용**으로
  측정한다. 첫 안정 레이아웃 후 650ms/2600ms 두 번, 최대 640뷰·깊이 9로
  제한. 어떤 화면 크기, 인셋, UI 프레임도 변경하지 않는다.
- 기대 이벤트 `guest_content_geometry_probe`: 프로세스 PID, 샘플,
  `root_guide_y`, `root_frame_y`, `root_safe_top_pt`, 화면 상단
  `top_controls`, `unsafe_controls`, `first_unsafe_control_y`,
  `scroll_top_without_inset`, `scan_capped`. 이름/문구/화면 캡처/게스트 ID
  수집은 금지한다. `unsafe_controls>0`이면 안전 영역을 실제 침범한
  컨트롤 후보의 경로를 추가 검증한다. **0이어도** SwiftUI 가상 요소나
  탐색 한계로 빠졌을 수 있으므로 시각 해결로 판정할 수 없다.
- R6P18은 화면 수정본이 아니라 **새 위치 계층의 원인 검증 빌드**다.
  실제 해결은 로그가 보여준 하위 콘텐츠 타입과 윈도 좌표에 대응하는
  독립적인 수정 및 실기기 사진/터치 검증을 거친 뒤 판정한다.
