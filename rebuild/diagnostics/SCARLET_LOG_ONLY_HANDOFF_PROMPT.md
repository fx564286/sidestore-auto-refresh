# P84 / L140 · 동일한 해결 방식 절대 차단 · 로그 한 장으로 이어서 실제 수정

> 최우선 신규 강제 규칙 (기존 P13의 "새 기기 증거가 있으면 같은 방법 재시도 가능" 예외보다 우선). **서로 다른 코드·파일·함수·타이머·버전도 결과적으로 동일한 제어 효과를 구현하면 동일한 방법이다.**

## 필수 실행 절차 — 로그를 제공받은 다음 모델·개발자에게

1. **실측과 변경 이력 확정:** `SourceCommit`, `CurrentSession`, `LogScope`, 현재 게스트 PID, 시행 전/후 시각별 위험 노드 수·상단 좌표·statusbar hidden·홈/재진입 여부를 정리한다. `REMEDIATION HISTORY` 전체 L001~마지막 항목의 수정 전후 `code_locations`와 SHA를 비교한다. 새 빌드가 실제 설치되지 않았다면 이전 기기 로그와 혼동하지 않는다.
2. **접근법 수준 분류:** 신규 변경의 동작을 `strategy_family`와 `operation_fingerprint`로 먼저 분류한다. 새 함수명·다른 파일·조건문 순서·타이머·이벤트명 등은 '새 방법'의 근거가 될 수 없다. 한 변경에 사용한 **모든** 핵심 보정 효과를 나열한다. 과거 시도와 같거나 원래 시도의 실패 조건만 완화한 조치면 즉시 중단한다.
3. **상단 문제 절대 금지 방식:** ① Safe Area/inset 추가·재계산 ② 상태바 강제 표시·숨기기·스타일 변경 ③ 헤더 위치/제약/transform 보정 ④ 스크롤 contentInset·contentOffset·frame·viewport 이동 ⑤ FBScene/원격 창 frame/scale/crop ⑥ 타이머·재시도·재검사 시점 변경 ⑦ 상단 오버레이/윈도우 마스킹 ⑧ 레이아웃 훅에서 기존 header/body를 다시 이동. L001~L139에 이미 기록된 방식이므로 **새 로그·별도 코드·다른 앱이라는 이유로 예외 허용 금지**. 문제를 눈에 안 보이게 가리는 것도 해결이 아니다.
4. **정말 다른 원인 3개 비교:** 기본 모드(정상)와 실험 모드(문제)의 *초기 화면 구성, UIViewController containment, guest render attachment, 프로세스·Scene 소유권, 라이프사이클* 구현을 실제 원본 소스와 비교한다. 최소 세 가지 **상이한 근본원인 가설/해결 구조**를 만들고, 각각 이미 시도한 Lxxx와 어떻게 다른지·검증 방법·기존 기능 회귀 위험을 기술한다. 단순 관찰/로그 추가를 최종 해결책으로 제시하지 않는다.
5. **원인 코드 교체:** 실제 원인이 발견된 경우에만 부작용이 가장 작은 하나의 독립적 실행 경로를 수정한다. 정상 모드의 경로를 근거로 삼되 일괄 복사·대규모 리팩터링·UI 추가는 금지한다. 사용 중인 V48 레이아웃, 멀티탭 A→B→A, 앱별 Apple ID 팀·인증서, IPA 설치, 오디오 분리, 키보드, 스크롤/터치/회전·기존 게스트 데이터는 보존한다.
6. **수정 전 CI 차단:** 새 proposal JSON에는 `incident_family`, `strategy_family`, `operation_fingerprint`, `source_behavior_contract`, `rollback_commit`, `normal_experimental_diff`의 실측·소스 증거, `alternative_strategies` 3개, `new_source_root_cause`, `runtime_acceptance_gate`, 그리고 정확한 `code_locations` 변경 전후가 필요하다. `python3 rebuild/diagnostics/scarlet_no_repeat_gate.py --proposal proposal.json` 반환 0이 아니면 코드 병합/빌드를 중단한다. `--repository-check`도 L140 이후 항목에 이 규칙을 적용한다.
7. **검증 3중 문턱:** (A) 기존 동작 회귀 테스트·전략 중복 차단 테스트; (B) Xcode 27.2 네이티브 컴파일·IPA ZIP·필요 앱 확장·버전·서명 범위 확인; (C) 서명 실기기에서 상단 겹침 0, 정상 시계/배터리, 전체스크롤/터치, 세로/가로, 홈 재진입, A→B→A 검증. A/B만 통과했다면 '소스/빌드 완료, 기능 해결 미검증'으로 기록한다.
8. **새 로그 인계:** 실행 커밋, 새 Lxxx, 고유 전략군, 실기기 결과와 미해결 항목, 시도하지 않은 다음 접근법, 정확한 실패 근거, rollback SHA를 덧붙여 기록한다. 다음 세션에서는 **동일 방법의 예외적 재적용도 기본적으로 차단**하고 독립적인 코드 경로를 선택한다.

**검사 한계:** 정적 게이트는 모든 임의 코드의 의미상 동등성을 수학적으로 검증하지 못한다. 따라서 허용 전략 목록과 변경 후 실제 수행 효과를 함께 대조하며, 분류가 불명확하면 자동 허용 대신 중단·재검토한다. 코드 자체를 새로 작성한 사실은 별개의 원인 증거가 아니다.

---

# 실행 우선·문제 해결 지속 지침 — 2026-11-14 P60 / L107

## 사용자가 명시한 목표

Scarlet Crystal 실험 모드 OFF에서는 정상인 게스트 앱들이 ON에서도 같은 정상적인 안전영역·시계·배터리·화면 배치로 작동하도록 **직접 원인을 연구하고 실제 실행 코드를 수정**한다. 인터넷에서 유사 사례를 찾거나 오류 검출용 코드만 추가하는 것으로 완료하지 않는다. 다음 채팅에서 이 진단 보고서 하나만 제공돼도 이전 상황을 반복해 요구하지 않고 동일한 실제 수정 작업을 수행한다.

## 새 채팅의 실행 순서 (강제)

1. 보고서 SourceCommit, CurrentSession, 현재 기기 증상과 마지막 Lxxx 수정 이력을 읽고 해당 빌드가 실제 설치된 것인지 먼저 구분한다. 최신 GitHub 소스를 열어 이력 상태와 정확한 소스 커밋을 비교한다.
2. L001~L107의 기존 실패 방법·실제 코드 위치·before/after를 확인한다. P37 단회 헤더 프레임 이동, P39 강제 제약, P44/P53 affine transform, 호스트 전체 콘텐츠 축소/투명띠, 추가 Safe Area 중복 적용, 상태 표시줄 강제 은폐 등은 장치 증거가 없는 동일 재시도를 금지한다.
3. **항상 실행 코드 수정이 주작업**이다. 기록용 이벤트만 추가하는 새 버전은 허용되지 않는다. 성공할 때까지 원인을 재모델링하고 새 인과 메커니즘을 설계·검증한다. 사용자에게 PC 조작을 요구하는 대신 저장소에서 가능한 작업을 먼저 수행한다.
4. 실제 기기 결과가 없는 테스트/컴파일/IPA 성공은 해결이 아니다. 정상 판정은 실기기에서 상단 위험 컨트롤 0, 정상 상태 표시줄, 가로·세로 및 홈 복귀 A→B→A, 전체화면/하단/스크롤·터치 보존으로만 한다.
5. L100 P54 신규 방식: 부모 UIViewController에 실제 게스트 커스텀 viewDidLayoutSubviews가 존재하고, 그 아래 50pt plain UIView 헤더가 Y0에 있는 경우, **단 하나의 부모 컨트롤러 인스턴스만 동적 서브클래싱하여 게스트 원래 레이아웃 구현을 먼저 실행한 후 그 부모의 native safeAreaLayoutGuide에서 헤더를 도킹**한다. 기존 P44 transform을 해당 대상에 중복 적용하지 않는다. 250/1350ms 실측 통과 시 retained, 실패하면 원래 클래스와 원래 프레임을 원복한다.
6. 실제 장치 로그의 guest_owner_layout_contract_staged / first_pass / retained / reverted와 원래 위험 컨트롤 수치, 앱 재진입 시 헤더 Y, 전체 콘텐츠/상태 표시줄을 대조한다. P54가 guest_owner_layout_contract_retained라도 위험 컨트롤이 0이 아니거나 실제 화면이 잘리면 **미해결**이며 L100의 같은 수정을 반복하지 않고 L101의 새로운 원인·실행 수정을 설계한다.
7. 새로운 후보는 수정 전에 scarlet_no_repeat_gate.py --proposal로 판정한다. 실제 변경 diff와 소스 SHA, 새 검증, 빌드/IPA, rollback, 다음 시도에서 피해야 할 원인까지 scarlet_remediation_history.json에 새 Lxxx로 기록한다. 그 JSON과 이 지침이 앱에서 내보낸 CURRENT RUN 공유 텍스트에 모두 내장돼야 한다.
8. V48 안정 기준의 번들 ID·원래 전체화면 크기·리사이징 금지·멀티탭·앱 간 RAM·색상/리퀴드 글라스·서명·오디오·키보드 동작은 별도 검증 없이 수정하지 않는다.

## P60 / L107: GitHub macOS 네트워크 실패에 대한 제한된 자동 복구

- P60 첫 원격 CI run 43563409847 SideStore checkout failed at 2026-11-14 05:50:17Z with literal git error "Could not resolve host: github.com". This is GitHub runner transient DNS failure, NOT an iOS source compilation result. Source SHA and pin checks have not run on this failed job.
- L107 modifies only the native CI workflow: LiveContainer / SideStore / StikPair fresh upstream git clones and two submodule updates get at most 4 attempts with 5/10/15 second bounded delays and explicit stop on last failure. The SHA pins, source integration, packaging, signed identities, original iOS native code, UI geometry, audio, keyboard, data remain untouched. Scratch checkout directories only are discarded after a failed clone attempt.
- CI build must pass genuine Xcode native compile, artifact merge and IPA readback; network retry is NOT proof the UI fix worked. 714 local tests (3 infrastructure skips) after adding two network guard tests.

## P60 / L106: 실기기 P59 실행 확인 이후의 깊은 공통 스크롤 소유자 재배치

- 2026-11-14 05:38:55Z 서명 실기기 세션 3e6fb95b는 Build 3.8.59 / SourceCommit 229e48d60bae로 P59 설치와 실행 성공을 확정한다. 로그 헤더에 남은 "P59 device not verified"는 빌드 시점 기록으로 최신 CURRENT RUN 관측에 의해 갱신됨.
- PID1881에서 guest_owner_layout_contract_staged/first_pass/retained, 처음 unsafe9 -> 2600ms unsafe6, status_hidden=true. P59의 guest_owner_content_reflow_staged 이벤트가 **전혀 없으므로** P59 부모 직접 자식 선택기가 새 본문 후보를 허용하지 않았음. P59 이전과 같은 unsafe6이며 상태바도 복구 안 됨.
- 2600ms ancestor chain: slot11 risk control y38 -> parent controller root y0 h956 -> slot12 nearest scroll parent y0 h956 -> 또 다른 nested full-screen scroll at depth5 -> root at depth8. 인접 body가 반드시 parent 직접 자식이라는 P59 가정이 이 구조에 맞지 않음. 또한 기존 bounded full-tree 24-level 탐색은 depth_capped=true, screen scan_capped=true이다.
- P60 **별도 실행 메커니즘**: UIControl/accessibility-button visible top risk를 56-level/2400-view 한정으로 실제 순회하고, 헤더를 제외한 모든 위험 컨트롤에 공통인 가장 가까운 UIScrollView를 찾아 P56의 직접 sibling 후보는 배제한다. 화면 전체 폭/높이, y0, 정상 스크롤 가능하고 contentSize가 충분한 원래 게스트 네이티브 scroll만 후보. 후보가 없거나 scan capped/모호하면 화면 수정 없음.
- 선정된 중첩 스크롤의 viewport만 원래 UIKit parent viewDidLayoutSubviews 완료 후 y=헤더 하단으로 정렬하면서 **하단 끝은 원래대로 고정**한다. 전체 UIWindow/FBScene/앱 규모/배경/상태바 속성/scroll.contentInset/offset/contentSize 등은 변경 안 함. 두 차례 안전성 검사에서 기존 unsafe 0 + 새 deep-level unsafe 0 + scroll contentSize/offset/inset 원형 + 위치/너비/하단이 모두 일치할 때만 유지; 어느 조건이든 실패하면 그 scroll.frame만 원복, 시계·배터리 shield 유지. 가로 회전 시 원래 프레임 복원.
- P59 단순 '24→56' 증가가 아니라 실제 위험 컨트롤들의 **공통 스크롤 조상**에 대한 새로운 소유권 기반 viewport 재배치이며, 앞선 P56/P59 원래 direct sibling 이동 반복을 금지한다.
- P60은 CI host CFBundleVersion=3.8.60, 원래 bundle ID/ShortVersion 유지, P57 게스트 덮어쓰기 및 기존 V48 시각 특성 유지. 신규 5개 + 전체 712개 로컬 테스트 통과(3 infra skip). Xcode 27.2 실 iOS compile, 배포 IPA ZIP/SHA, 다음 서명 실기기에서 stage -> two pass unsafe0/status_hidden=false/기존 스크롤·스크린샷·A-B-A를 확인하기 전에는 해결 판정 금지.

## P59 / L105: 실제 위험 컨트롤을 소유한 스크롤 본문만 선택

- 2026-11-14 04:53:47Z signed-device session a81ec965 still SourceCommit bed3419b9dd4, Build 3.8.11, despite P58 being available at 04:39Z. No proof that P58 was actually installed. Do not claim success until a signed device confirms P58+ SourceCommit and the increased CFBundleVersion.
- P56 guest PID1433: guest_owner_content_reflow_staged then reverted at 250ms, while guest_owner_layout_contract_retained; top-unsafe controls 9 down to 6 but six remain in scroll, and status_hidden=true. P56 selected the parent scrolling sibling only from geometry; it did not verify the selected sibling actually owned those other six unsafe controls.
- New actual runtime method: ScarletIslandP59VisibleRiskInSubtree walks each original direct sibling's interactive descendant risk, and ScarletIslandP59UniqueRiskNativeBody selects the one scroll-backed body owning ALL residual unsafe controls outside the proven header. Refuse multi-owner, scan-cap, geometry-ambiguous, non-scroll, or candidate identical to the already-failed P56 geometric body. Do not perform a same-candidate retry.
- Reuse already-proven bounded parent-native callback, fixed bottom edge and P56 two-pass 0-unsafe safety gate ONLY on the independently identified risk-owning body. Restore original body on nonzero risk. Never alter UIWindow/FBScene/root scale, scroll contentInset or contentOffset, window colors, credentials, signing assets or guest data.
- P59 host CFBundleVersion 3.8.59 in CI, same host Bundle ID and ShortVersion 3.8.11, with P57 queued guest overwrite preserved. Local suite 707 tests passed (3 infrastructure skips). CI native compile, posted IPA SHA, signed device and visual clock+battery+scroll+touch remain separate evidence gates.

## P58 / L104: 호스트 설치 식별

- P56 and P57 both set host CFBundleVersion=3.8.11. P58 changed only host CFBundleVersion to 3.8.58; the public IPA was confirmed ZIP-correct with identical app bundle ID and SHA file, but device side installation remains unverified. SideInstaller can install over the same bundle identifier while preserving app data, but the current Scarlet log contains no SideInstaller install receipt. Do not uninstall existing app or revoke signing certificates.

## P57 / L103: 동일한 게스트 IPA 덮어쓰기 실제 수정

- 새 사용자 보고: 동일 게스트 IPA를 다시 설치하면 업데이트가 되지 않음. 첨부 세션 7105e9c3에는 게스트 IPA 설치 이벤트가 없어 실기기 원인 확정은 아님.
- 확인된 코드 결함: Scarlet의 원본 LCAppListView 파일 가져오기 워커는 1x1 픽셀, 완전 투명, 터치 차단 상태. 원래 LiveContainer는 기존 동일 Bundle ID를 발견하면 installReplaceAlert.open()의 사용자 선택을 기다리므로 진행이 정지할 수 있음.
- P57 실제 소스 변경: queued Scarlet IPA일 때 설치된 동일 ID 게스트가 정확히 하나면 기존 상대경로로 교체, 여러 개/잠긴 숨김 앱/실행 중인 앱이면 차단하여 사용자에게 명확한 오류 표시. 원본 LC가 보이는 화면에서는 기존 사용자 선택 그대로 유지.
- 기존 앱 보존 트랜잭션: 동일 볼륨 임시 .app에 새 바이너리 이동 및 서명 완료 → 종전 설정/dataUUID/containerInfo/tweaks/언어/잠금 복사 → 기존 .app 숨김 백업 → 새 바이너리를 같은 경로로 교체 → Bundle ID와 dataUUID 재검증 → 실패 시 백업 복원. 게스트 사용자 데이터, 인증서 및 페어링 파일 삭제 없음.
- 검증: 변경된 원본 pinned LC 소스 생성 경로 테스트, 697개 전체 로컬 테스트 통과(3개 환경상 skip), 구체적인 설치 단계는 기기 검증 전까지 성공 아님. 새 로그의 guest_import overwrite_single_match_selected / overwrite_committed / overwrite_sign_failed_preserved / overwrite_rollback_restored를 확인.
- P56 상단 Safe Area 수정은 P57에 포함되어 유지된다. 다음 새 로그만으로 P56 헤더와 P57 게스트 덮어쓰기 모두 이어서 처리한다.

## P56 / L102: 서명된 P55의 부분 성공 이후 콘텐츠 소유권 수정

- 2026-11-14 서명 실기기 로그 SourceCommit 54d24ab2b20a, 세션 99565816, PID2293에서 parent layout owner 수정 staged/first_pass/retained가 확정되었음. 650ms 위험 컨트롤 9개 → 2600ms 6개 유지, Instagram 스토리 위에 wordmark가 겹친 화면과 시계·배터리 숨김은 미해결. 상태바가 자동으로 보인 다른 PID2305에서는 위험 컨트롤 0개와 status_hidden=false가 확인됨.
- **L102 기능 변경:** 기존 P55는 헤더 y만 부모 safe guide로 옮겼고 실제 스크롤 본문은 원래 y50 근처에서 움직이지 않았다. P56은 같은 원래 UIKit 부모 viewDidLayoutSubviews 실행 직후, 헤더와 같은 부모에 있는 유일한 전체폭 스크롤 본문을 헤더 아래로 정렬하며 그 본문 하단은 고정한다. 게스트 UIWindow/FBScene/루트 크기 1.0 배율, contentSize/contentOffset/contentInset, 원래 하단탭, 인증/오디오 등은 바꾸지 않는다.
- **원복 조건:** 스크롤 본문 후보가 한 개가 아니거나 없으면 P55 헤더만 유지. 후보가 있더라도 첫 250ms 및 두 번째 1350ms 모두에서 실제 위험 컨트롤 0, 헤더 아래 스크롤 본문 정렬, 원래 하단, 동일 PID 및 전체화면이 확인되지 않으면 본문만 원복한다. 이전 P44 affine/host crop을 재시도하지 않는다.
- **시계·배터리:** 처음 650ms 위험 때문에 저장된 P51 sticky statusbar collision shield는 단순 후속 unsafe0으로 풀지 않는다. P56의 독립적인 두 번 연속 native owner + feed 실제 unsafe0 확인 및 활성 PID 매칭시에만 해제한다. `guest_owner_content_reflow_retained`와 `resident_native_status_bar_verified_reflow_readback(status_hidden=false)`가 모두 확인돼야 복구.
- 사용자에게서 새 로그만 오면 `guest_owner_content_reflow_staged/first_pass/retained/reverted`, `guest_content_geometry_probe(visible_unsafe_controls)`, 시계·배터리 및 스토리 겹침 실화면을 읽는다. 본문 후보 없음/되돌림인 경우 기존 P55보다 후퇴시키지 않고 다음 L103에서 실제 화면 계층을 근거로 다른 소유권 수정 코드를 작성한다. P56은 소스 빌드 통과와 실기기 정상화가 아직 별개이다.

## P55 / L101: 실제 P54 로그에서 발견된 실행 분기 불일치

- 실기기 소스 fc2fd271b9e8, 세션 990090a7, PID1841의 header_controller_parent_match=1은 문제의 50pt Y0 헤더가 plain UIView가 아니라 자식 UIViewController.view임을 입증한다. parent custom viewDidLayoutSubviews origin3, parent native safe guideY62가 같은 샘플에 존재한다.
- P54 코드는 owner 수정 진입을 headerKind==2로 제한하고 header.nextResponder==parent를 강제했으므로 이 로그에서 owner contract가 실행되지 않았다. 실제 로그는 P44 affine unsafe9→6 뒤 reason2 invalidated이며, guest_owner_layout_contract_* 0건이다.
- P55 코드 변경은 이 미실행 대상만 parent.viewDidLayoutSubviews 원래 콜백 후 native guide 도킹으로 진입시키는 **소유권 분기 실제 동작 수정**이다. 헤더의 child UIViewController가 parentViewController인 것, 높이50±4, 부모의 custom layout override 등 기기에서 측정된 조건만 허용한다. owner 경로 거절 시 이전에 실패한 P44 변환을 반복하지 않는다.
- P55 사용자 기기 성공 미검증. Xcode/IPA 성공도 실제 게스트 위험 컨트롤 0과 상태바·터치·스크롤·회전·A→B→A 증거가 아니면 해결 아님. 이후에는 guest_owner_layout_contract_staged/first_pass/retained/reverted 및 화면 시계/배터리 결과를 확인한다.
- P55에도 여전히 UI가 위험하면 같은 frame/transform/inset/crop을 다시 적용하지 말고, 자식 컨트롤러의 실제 부모 레이아웃 제약 쓰기 지점을 연구한 L102 기능 수정으로 진행한다. 같은 로그만으로 작업 지속 가능하도록 이 L101와 전체 소스 diff/검증 범위를 JSON에 유지한다.

## 현재 연구 결론과 반증 조건

- 2026-11-14 P53 소스 6816d81eb66f4884d22d4a90e7709188fca88e28 및 서명 실기기 로그: iPhone 440x956, root/parent safeTop62, 문제 short header Y0/높이50, 위험 컨트롤 약9개. 실제 P53 보정은 9→6 일부 개선 뒤 local affine transform invalidated (reason2). parent UIViewController가 앱 자체 viewDidLayoutSubviews 구현을 가지고 있어 after-layout 변형이 덮이는 원인 후보이다.
- P54는 전역 swizzle이나 62pt root inset/host scene crop이 아니라 이 특정 부모의 레이아웃 **소유 지점에 개입하는 실행 수정**이다. 클래스/헤더 대상이 정확하지 않으면 해당 조치는 생략한다.
- P54 성공 가설: 자연스러운 레이아웃 완료 후 부모 safe guide의 y62에서 헤더가 지속돼 상단 위험 컨트롤이 실제 감소하고 터치도 안전하다. 이후 1회라도 다시 Y0에 있다면 실패; P54 경로 재도전이 아니라 다른 실제 원인 조사.
- 보고서 첫머리 NEXT ENGINEERING ACTION의 검증 상태는 해당 빌드 설치 여부를 판단하는 데 사용한다. 런타임 기록이 없는 신규 P54 빌드에 대해 해결이라고 주장하지 않는다.
- P54 뒤에도 신뢰할 수 있는 실제 기기 수치가 없으면 가능한 소스/시뮬레이터/CI 검증을 우선 실행하고 미검증 사실만 구분한다.

---

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
이미 실행한 방법을 다른 이름으로 다시 적용할 수 없다. P84 이후에는 **같은 동작 방식 자체의 예외 재시도를 허용하지 않는다**. 새 기기 증거가 나오면 예전 방법을 재사용하지 말고, 그 증거에서 실제로 다른 원인·전략군을 도출한다.

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

## 10. R6P18 동일 SourceCommit 내부 권한 변화 및 R6P19 독립 조치

- 2026-11-12 05:57:04 UTC 제출된 `CURRENT LAUNCH` 및 `ARCHIVED LAUNCHES`
  로그 2개 모두 상단 `SourceCommit=476892cec6cf`다. 그러나 이 헤더는
  **현재 설치 빌드**를 뜻하며, archived JSONL 각 세션의 build SHA를
  소급해서 증명하는 값이 아니다. R6P18의 guest geometry 이벤트가
  archived 옛 세션에서 누락됐다고 곧바로 P18 진단 실패로 볼 수 없다.
- UTC 05:55 `session.1.jsonl`: 서명 사전검사 `entitled_app_group=true`,
  `group_accessible=true`, `certificate_present=true`, `team_match=match`.
  UTC 05:56 `session.0.jsonl`은 `entitled_app_group=false`,
  `group_accessible=false`, `certificate_present=false`, `password_present=false`,
  `signed_host_identity=match`, 이어 `sidestore_app_group_not_entitled`와
  JIT-less 실행 차단. 소스 커밋이 동일하므로 코드를 바꾼 사실 자체는
  원인이 아님. 단, 정확한 설치/재서명 변경은 signed IPA의
  entitlement/profile readback 전까지 원인 확정 금지. 기존 Keychain,
  게스트 데이터, Apple 인증서를 삭제·폐기하지 않는다.
- 필요한 Apple 실제 권한:
  `com.apple.security.application-groups`에
  `group.com.SideStore.SideStore.P8EZT3U5N4`, 서명 팀 `P8EZT3U5N4`,
  앱 ID `com.kdt.livecontainer.P8EZT3U5N4` 및 기존 확장 구성.
  IPA 릴리스는 UNSIGNED이며 이 앱 코드만으로 권한을 만들지 못한다.
  `rebuild/scripts/audit_signed_ipa_entitlements.py --signed-ipa ...`는
  macOS에서 Apple codesign + embedded.mobileprovision을 모두 검사한다.
- UTC 05:56:39 2FA는 제출됐으나 `-3402 / sidestore_team_recovery_failed`,
  이후 게스트 `jitless_signing_certificate_missing`; **로그인 성공·팀
  복원 성공이라고 보고하지 않는다**. App Group 권한 없는 상태에서
  인증서 선택이나 Apple 로그인 재시도를 정답으로 안내하면 안 된다.
  R6P19는 앱 내 차단 사유를 실제 signed entitlement 누락으로
  구분해 알려준다. 재서명 자체는 구현하지 않았으므로 차단이 남는다.
- 여러 이전 세션 및 현 세션에서 HTTPS 소스 다운로드가
  `NSURLErrorDomain -1005`로 반복 실패한다. R6P19는
  **그 에러만** 최대 2회 재시도하며, resumeData가 있으면 이어받기;
  복구 불가 코드에 한하여 새 다운로드로 후퇴. 시도 횟수·방식만
  로그에 남기고 URL/게스트 이름/파일명은 남기지 않는다. 서버가
  지속해서 끊으면 그대로 실패하므로 네트워크 성공은 기기 로그
  `guest_download_completed`로 따로 검증해야 한다.
- UTC 05:54:29에 이전 세션의 게스트 PID `4788`은
  `fullscreen_scene_process_exited(fast_exit=true,duration_ms=107)`;
  iOS crash `.ips`가 없어 원인 규명 불가. 이 건을 권한 문제나
  Safe Area 문제와 혼동하지 않는다.
- R6P18의 `guest_content_geometry_probe`는 **현 세션에는 게스트가
  실행되지 않았으므로 평가 불가**. 권한 정상인 Apple 서명 빌드로
  실행 성공한 뒤 실제 PID별 측정 여부를 다시 확인한다.

### 10-A. R6P19 Xcode 27.2 실컴파일 차단 원인 및 원인 한정 보정

- 최초 R6P19 GitHub Actions run `43166177133`, LiveContainer job
  `131008464808`: Xcode 27.2 native archive **exit 65**.
  다운로드한 실제 원본 `livecontainer-build.log`:
  `ScarletIntegratedHostView.swift:919:42: error: cannot find
  'NSURLErrorCannotResume' in scope`. 이 에러 상수는
  pinned Foundation SDK에서 사용할 수 없다. 테스트 519건 PASS는
  Swift 네이티브 컴파일 증거가 아니라는 차이를 명시한다.
- 실제 코드 위치: `downloadSourceWithConnectionRecovery`,
  `session.download(resumeFrom:)` catch 블록. 존재하지 않는
  `NSURLErrorCannotResume` 비교를 제거하고 **실제 NSError domain이
  NSURLErrorDomain인 경우 중 사용자가 취소한 `NSURLErrorCancelled`는 제외**.
  재개 시도에서 오류가 발생해도 이미 검증된 동일 HTTPS URL을 딱 한 번
  새로 다운로드하며, SSL 검사/IPA ZIP 서명·내용 검증은 변경하지 않는다.
  일반 -1005 재시도 역시 기존 3시도 상한 안에서만 동작한다.
- 기존 L055, L056은 그대로 보존. Xcode 실컴파일 증거가 신규이므로
  L057에 신규 커밋과 정확한 diff를 별도 남긴다. 최종 CI 통과와 기기에서
  실제 네트워크 성공은 여전히 독립적으로 확인해야 한다.

## 11. R6P20: 인증 세션 재사용·백그라운드 signed Bundle ID 경로

- R6P18 2026-11-12T05:56:43Z `-3402` 팀 복원 실패. 고정 SideStore
  `AuthManager.signIn`은 `(account, ALTAppleAPISession)`을 반환하지만
  그 결과를 `AuthManager.shared.session`에 저장하지 않는다.
  그 직후 호출한 `DeveloperPortalProxy.fetchTeams(for:)`는
  `AuthManager.getAuthenticatedSession()`이 캐시가 없으면 새로운
  `AnisetteProvider.fetch()`를 실행하는 별도 네트워크 경로를 탄다.
  R6P20은 이미 2FA 성공 및 Keychain readback 통과된 **동일 세션만**
  기존 SideStore 메모리 캐시에 저장한 뒤 팀 복원을 실행한다.
  타인 계정/다른 팀 자동 전환·인증서 폐기·OTP 저장 없음. 새 실기기
  로그에 `-3402`가 다시 남으면 이 가설은 해소책이 아니므로
  포털/DB 단계별 실패를 분석해야 한다. App Group 권한 부재를
  해결하는 수정이 아님.
- R6P18 현 세션 `automatic_background_registered(unavailable)` vs
  여러 옛 세션 `registered`. 별도의 부호는 기존 서명기가 사용자의
  Bundle ID에 `.P8EZT3U5N4`을 덧붙이는 변형을 만들 수 있다는 것.
  원래 BGTaskScheduler identifier는 기본 번들에 고정돼 있었다.
  R6P20은 **이미 승인된 두 가지 ID에 한해서만** 실제
  `Bundle.main.bundleIdentifier`에 `.refresh`/`.pairing`을 붙이며
  같은 두 variant를 `BGTaskSchedulerPermittedIdentifiers`에 추가한다.
  서명 App Group, BG 실행 권한, 새 App ID, iOS 스케줄은 변경하지
  않는다. 다음 실행에서도 `unavailable`이면 실제 signed Info.plist와
  OS 제약을 확인하고 같은 ID 변경은 재시도하지 않는다.
- 원인별 신규 코드 기록은 L058(인증 Apple session 사용)과
  L059(BGTask Bundle ID 선택)로 분리한다. R6P18 하위 콘텐츠
  지오메트리 `guest_content_geometry_probe`는 다시 실행 성공한
  게스트에서만 판단한다.

## 12. R6P20 최신 실기기 증거 · R6P21 깊이 탐색 누락 및 SideStore 인증서 재판정

- 최신 R6P20 실기기 파일 `붙여넣은 텍스트(1)(20261112-065038).txt`:
  SourceCommit=`7212364c7c65`, session=`19667412`,
  iOS 27.2 (24B119), 2026-11-12 06:49:28~06:50:30 UTC.
  **현재 실행의 JSONL 203개 이벤트**. 60개 이전 L001~L060 이력이 완전
  포함돼 있으며, 과거 안전영역·SDK/overlay 보정 반복 금지.
- 이번 실제 성공: `automatic_background_registered(registered)` 및
  scheduled, `pairing_restored(pairing_saved_and_transport_ready)`, Apple
  `twofactor_code_submitted`→`stored_session_verified`→
  `host_session_restored`, 게스트 PIDs `5497`/`5506` 모두 실행,
  `entitled_app_group=true`, `group_accessible=true`, LC P12 true,
  `signed_host_identity=match`, `team_match=match`, 각각 루트 Safe Area 62pt.
  게스트 앱 A→B에서 `recent_session_registered` 1→2 누적 기록.
  `switch_panel_content_rendered=2`, `switch_panel_recent_rows_mounted=1`은
  **현재 앱 1행을 별도 렌더링하므로 정상**. 이를 버그로 분류하지 않는다.
- 다이나믹 아일랜드는 **시각적 미해결**. `guest_content_geometry_probe`
  PID5497은 `visited=46`, `candidate_controls=7`, `unsafe_controls=0`,
  `scan_capped=true`; PID5506은 `visited=15`, `candidate_controls=0`,
  `unsafe_controls=0`, `scroll_top_without_inset=3`, `scan_capped=true`.
  650ms/2600ms 모두 동일. 실제 구현 L054는 깊이 9에서 중단하므로
  두 프로세스 모두 뷰 개수 640에 도달한 것이 아니라 **깊이 잘림**.
  이전 `unsafe_controls=0`은 가림 없음의 증거가 될 수 없다.
  R6P21은 깊이 24/노드 1200으로 제한된 읽기전용 관찰,
  `depth_capped`/`count_capped`/`max_depth_seen`, 익명 상단 UILabel/
  UIImageView 등 시각 노드 프레임, 초기 y 좌표 및 스크롤 위치를 수집.
  루트/UIWindow/액세서빌리티/스크롤 인셋 변경은 없다. 별도 로그·화면
  확인 없이 가림 해결이라고 표시하지 않는다.
- `sidestore_managed_apps_inspected(count=1, signing_ready=false,
  reason=sidestore_certificate_missing)`는 UTC 06:50:00과 06:50:07,
  **인증서 조회보다 이전**. UTC 06:50:08 Native provider는
  `existing_portal` P12를 반환하고 LC에 이미 같아
  `native_provider_same_certificate`가 나왔으나 이후
  `ScarletNativeRefreshInspector.inspect` 재검사는 없었다.
  **SideStore 인증서가 계속 누락됐다고 확정할 수 없다.** R6P21은
  기존 인증서 조회 완료 직후 원본 SideStore Keychain·관리 앱 읽기 경로를
  재실행해 `certificate/sidestore_signing_rechecked`에
  `count`, `host_managed`, `signing_ready`, `reason`을 별도 기록.
  인증서 재발급/폐기/복구를 임의로 반복하지 않는다.
- `installation_verified=false`는 자동 갱신 재시도 간격 때문에
  이번 실행에 설치 확인이 없었다는 뜻. BGTask 예약 성공과 실제 앱
  프로파일 갱신은 다르다. 새로운 iOS `.ips` 크래시나 네트워크 -1005는
  이번 실행에는 없으므로 이전 실패를 새 재현으로 오인하지 않는다.
- 신규 수정 이력은 L061(한계를 실제 iPhone에서 반증한 하위 콘텐츠
  좌표 관찰) / L062(인증서 provider 이후 SideStore 상태 재확인)이며,
  각각 GitHub 정확한 SHA와 before/after unified diff 기록 필수.

## 2026-11-15 · P63 signed-device readback and P64 handoff
- User upload (2026-11-14 18:50:38 UTC) P63 build 3.8.63; source b09aa169b56f;
  CURRENT LAUNCH session 263e2ce2; 1,005 JSONL events.
- Guest PID1798 650ms: rootSafeTop62, unsafeControls5, inset0.
  Native P54 parent header contract staged, first pass, retained, unsafe 5->2.
  At 2600ms: unsafeControls2; first unsafe y58 vs root safe guide y62;
  fullpage scroll owner frameY0 height100%, native content and adjusted inset58,
  offsetY-58, explicit .never (2), scrollEnabled1, contentHeight383%.
  Depth capped at24 (coverage not complete).
- Guest PID3873 650ms and 2600ms: unsafeControls0, root safeTop62,
  scan uncapped, native status_hidden=false observed. An unsafe image
  outside scroll remains, so visual perfection NOT proven.
- Guest SDK user override PID1798=27.1 vs PID3873=26.4.
  This difference is not proof of SDK-based root cause; no arbitrary SDK changes.
- A/B recent session count reached2, switcher content rendered2, reported audio
  pause/resume OK acknowledgements, not acoustic separation proof.
  Pairing transport alternated unavailable/restored. Automatic native worker
  reported native_profile_date_advanced_install_unverified and
  installation_verified=false, not a verified successful installation.
- Historical L063/L071 scroll.contentInset direct writes, L072 automatic
  adjustment policy and P54-P63 parent/deep viewport attempts did NOT solve
  the residual P63 2-control y58 case; do not repeat these exact changes.
- P64 novelty: select ONLY after the P54 original controller-owned header was
  anchored to the native safe guide; reject if not 1..4 narrowly unsafe
  visible controls or if they do not share a true fullscreen scrolling owner.
  Require 2..10pt measured gap, existing native near-safe inset, original
  scroll offset anchor, scroll enabled and stationary, root safeTop confirmed,
  no layout scan capping. Reflow ONLY this scoped scroll's native VIEWPORT
  origin.y += gap and height -= gap, retaining its bottom edge; leave
  scroll contentInset, contentOffset, adjustmentBehavior, root scene/window,
  colors and V48 scaling untouched. Retain existing per-instance parent
  layout completion hook and two independent zero-risk verification gates.
  If either gate fails, restore original viewport/frame and original class.
- New expected receipt: guest_owner_content_reflow_staged with reason
  p64_post_header_residual_viewport, then guest_owner_content_reflow_first_pass
  and retained; two consecutive zero-unsafe readbacks, status bar visible,
  scrolling and rotation pass. A staged receipt is NOT a successful device fix.
- P64 Xcode native compile and real iPhone confirmation remain required.
  Unsigned IPA is not installable without proper Apple signing.

## 2026-11-15 P64 signed iPhone confirmation and P65 new code
- Fresh device export 2026-11-14 19:24:26 UTC, build 3.8.64,
  SourceCommit 8518c552e03c, session c7732019, PID5205.
- Native 650ms unsafe 8, images 7, initial control y3. Parent 50pt
  child controller header was actually staged and P54 layout retained
  (unsafe after header: 5); P64/p60 native body staging reverted.
  2600ms unsafe1 images0, first control y50 vs 62pt safe guide,
  full native scroll top inset 50, offset -67, top content size432%,
  scroll enabled, scan capped at depth24. Status_hidden=true.
- Crucial P64 source defect beyond that device: P64 stores
  state.body_kind=64, but P63BindNestedParent allowed ONLY kind60.
  Thus P64's new candidate could never be bound even when the
  !nativeBody precondition was satisfied. P65 fixes allowed types
  60/64/65; static tests verify this exact guard.
- P64 also only evaluates the 1..4-risk residual path while
  !nativeBody, so when old p60 candidate exists but its proof fails,
  the P64 path cannot recover afterward.
- P65 introduces a separate solution conditional on a FAILED original
  native body, RETAINED original P54 header and a post-2600ms native
  UIWindow. Select a FULL-viewport common scroll enclosing exactly
  1..3 unsafe interactive nodes y=(safeTop-28..safeTop-2), with pre-
  existing real adjusted and content top insets near safeTop.
  Require 2 independent settled UIScrollView states, no tracking,
  dragging or deceleration, and offset within3pt of native -inset.
  Only 4 bounded retry opportunities after 2600ms, not a global hook.
- Formula for the distinct P65 native lever:
  corrected scroll viewport top = headerBottom - original
  adjustedContentInset.top. Example headerBottom112 and native
  inset50 => scroll frame origin +62 (not +112 as P60 tried).
  This preserves the original scroll content inset, offset, size,
  UI scale, UIWindow and FBScene geometry; reduces scroll viewport
  height by exactly that Y displacement, retaining bottom edge.
  Apply within existing parent UIView.layoutSubviews after its IMP,
  per-instance. Reject any other unknown scroll owner.
- Require first and late native proof with original contentSize and
  contentInset intact, header y62, scroll effective content y112,
  complete bounded risk walk, unsafeControls0, unsafeImages0 and
  stationary native offset. If either fails, restore exact previous
  scroll.frame and unbind the scoped dynamic parent subclass.
  Only the two-pass retained receipt can allow host native status icons.
- Original V48 visual/switcher/color and signing assets unchanged.
  Local tests and CI build do not prove guest success. Next on-device
  run must compare PID sample650/2600, verified P64 kind64 binding
  if selected, optional P65 settled compensation receipts, clip/scroll
  touch behavior, orientation, A/B switcher, clock and battery.
  No icon release without TWO zero-risk proofs.

## P66 / L114 — 로그인 안내창 제거 및 SideStore 다중 계정 실사용 경로

- P65 설정의 `추가 로그인`은 실제 로그인 대신 `scarletShowAccountAdditionNotice`만 열었음. P66에서 `scarletShowAppleLogin`으로 교체함. 로그인 시트에는 별도 Apple ID 추가 및 저장 계정 목록/명시적 활성 전환 기능을 연결함.
- 원본 SideStore `AuthManager` 단일 활성 Keychain은 유지. `ScarletGuestSavedAccounts.swift.txt`를 *원본 AuthManager.swift 같은 파일*에 주입하여 기기 전용 Keychain에 개별 인증 슬롯을 저장하고, 원본 CoreData 계정/팀과 완전 일치할 때에만 전환. 실패하면 이전 슬롯 복원.
- 추가 계정은 Apple 포털에서 실제 소유한 Team을 허용. 반면 기존 Scarlet 호스트의 앱 재서명/자동 갱신은 `requireHostTeam=true`로 P8EZT3U5N4 유지. 인증 토큰, OTP, 비밀번호는 로그, UserDefaults, XPC 계정 목록에 복사하지 않음.
- SideInstaller.ipa(v2.0.1)와 LCSign-1.4-7.ipa(v1.4/7)를 정적 REA해 AccountStore/PairingManager, CertificateStore/IPAInstaller/BackupRestore 기능을 확인함. 바이너리 또는 사유 코드를 Scarlet에 복사하지 않았음. 자세한 증거와 해시: `rebuild/reports/SCARLET_P66_REA_AND_FUNCTION_AUDIT_20261115.md`.
- P66 코드 변경 커밋은 L114 source_revisions에 정확한 GitHub SHA로 기록. 전체 Python 테스트 744 실행(741 통과·3 skip). GitHub CI Xcode native compile 및 iPhone 실기기 2FA/계정 A→B→A/서명 및 전환 후 재진입 결과는 미검증. P65 상단 잘림/상태바 문제를 해결했다고 기록하지 말 것.
- 중복 금지: 버튼 활성화/안내창 문구만 변경하거나 CoreData 계정 row만 추가하고 보안 토큰·활성 팀 XPC 스위치를 빠뜨리는 작업. 추가 로그인 실패 시 기존 활성 계정, 인증서, 게스트 데이터 삭제 금지.

## P67 / L115 — 로그인 실패 롤백 보장 및 실제 릴리스 배포 변수 복구

- P66 signed-device 검증 이전 코드 재감사에서 새 Apple ID의 Keychain round-trip 검증 실패 경로가 `finish(...); return`으로 안쪽 트랜잭션 catch를 건너뛰어, 이전 활성 계정 복원 자체가 실행되지 않는 명확한 버그를 확인함. P67은 해당 실패를 `throw NSError(...,-3401)`로 바꿔 기존 catch에 도달하도록 수정.
- 계정 전환 후 이전 계정의 Keychain/CoreData 복원도 실패하면 `rollback_unverified`로 상태를 구분. 복원 성공이라고 허위 표시하지 않고 사용자에게 다시 계정을 점검하도록 알림. 원본 토큰, 인증서 삭제 금지.
- P66 native CI GitHub Actions run `43656279912`: SideStore/native LiveContainer/package-paired 3개 작업은 각각 성공. 릴리스만 실패: `line 283: asset: unbound variable`, P66 tag 분기에 `asset` 미할당. P67은 P66/P67 릴리스 분기 각각에 실제 IPA 파일명을 지정하고 3.8.67 별도 CFBundleVersion/tag를 사용. 이 수정은 실사용 로그인·설치 테스트를 대체하지 않음.
- P67 새 소스/정확한 diff와 SHA, CI 검증은 L115 `source_revisions`, `code_locations`에서 참조. P66의 게스트 상단/시계·배터리/오디오 미해결 문제는 별도 검증 대상으로 유지.

## P68 / L116 — 로그인 2개면 설치 개발팀도 2개로 실제 분리

- 실제 3.8.67 사용자 로그 `2026-11-15 00:27:25 UTC`, session `8236de81`, SourceCommit `1bc2e0b6bd85`: 두 번째 Apple ID의 `twofactor_code_submitted`와 `stored_session_verified` 성공 이후 `install_failed(reason=team_mismatch,stage=team,worker_stage=certificate_loaded)` 발생. 수동 갱신 2회·자동 갱신도 `sidestore_team_mismatch`로 실패. 증거는 계정 B의 실제 Team ID나 B 인증서 P12 존재까지 증명하지 않음.
- P67 ‘로그인만 다중화’에서 빠졌던 설치팀 연결이 문제의 본질임. P68은 설치 버튼→저장된 Apple 계정/각 계정의 실제 Team ID 선택→계정 token/Team 전환→일치하는 서명 P12 준비(또는 사용자가 명시적으로 인증서 발급)→IPA Files 선택→XPC `expectedTeamID` 검증→원본 SideStore AppManager 실제 설치로 연결.
- 기존 호스트의 서명팀 P8EZT3U5N4는 iOS entitlement/App Group을 증명하는 주체이지 Apple ID B의 일반 앱 설치팀이 아님. 이 두 개념을 섞어서 B 설치를 막지 말 것. 대신 B로 A의 이미 설치된 Scarlet 자체를 재서명하는 것도 금지. 앱 갱신은 원본 InstalledApp.team과 현재 선택 팀의 교집합만 사용.
- `ScarletInstallTeamAuthority`의 X.509 subject Organizational Unit 정확히 일치 검사, 만료확인, 기존 P12 보존, 선택 팀 readback, TeamOperationGate 직렬화를 유지. 인증서/OTP/Apple 암호/개인키는 XPC 응답/로그로 보내지 않음.
- 상세 파일·함수 diff는 L116 기록, 재현 로그 원인과 범위 및 서명된 실기기 수락 조건은 `rebuild/reports/SCARLET_P68_TWO_ACCOUNT_INSTALL_TEAM_20261115.md`. P67 UI 상단/상태표시줄 미해결을 P68 인증 작업의 성공으로 표기 금지. 별도 실제 iPhone A/B 설치 테스트 필요.

## P69 / L118 — 중복 기능/상태 라벨 제거, 실제 동작 유지

- Signed P68 session cb9cabf6 shows login/pairing restore, `native_provider_failed` code0 and fallback `native_provider_same_certificate`; refresh deferred, `status_hidden=true`, A/B actual IPA install unproven. The previously exported log's NEXT ENGINEERING ACTION block was generated before P68 native CI passed; treat current CI independently.
- P69 modifies **visible SwiftUI labels only** (and unique 3.8.69 native CI release routing). Settings removes independent signer-ready caption, automatic-refresh count/registration rows and redundant signer-ready line; only shows `최근 갱신` following a real attempt and one failure message. Keeps manual refresh, certificate issue/import, pairing, original settings and stored-account selection XPC untouched. Removes false P68 slot warning; account picker only warns when P12 missing.
- Source commit `4b1808a75a363654d84060d528b559f2114bd3e9`. All 16 changed source paths/byte-for-byte before and after are recorded as L118 code_locations. Local 758 Python tests (755 passed,3 skipped), YAML parse passed. Real P69 iPhone and native Xcode are not yet evidenced in this record.
- Important: **do not** reintroduce deleted passive status labels to satisfy old source-string tests. Maintain one owner for every action and keep runtime failures in one visible place, full JSONL diagnostics. Do not treat `certificate code0` or `status_hidden` as fixed by this UI change.


### L145 · P87 account UI/p12 diagnosis (2026-11-16)
- Device P86 receipt: `import_blocked/password_or_team_mismatch` twice; `host_selected_team_mismatch` during automatic refresh; `account_certificate_team_readback/ready_existing_portal` is portal/Keychain readiness, **not** proof of a manually imported per-account p12.
- Root cause of manual import: `ScarletSigningReadinessPanel.importExportedP12` compares imported p12's Team with `LCSharedUtils.teamIdentifier()` (signed HOST), not selected SideStore account Team. This legacy `LCCertificateData` slot is host-wide. Replacing with another Team breaks host/guest signing. P87 separates p12 decode failure from host-Team mismatch without claiming second-Team import works. A new per-Team SideStore Keychain import transport and signed-device readback are still REQUIRED. Do not repeat a local-global UserDefaults write for another Team.
- UI: P85 injected manual Divider in a single native Form cell, visible short line under active status. P87 removes that divider and spaces rows. Settings account switch success posted `ScarletGuestAuthVerified`, triggering redundant account readback; P87 performs certificate preflight directly and retains verified rows.
- New implementation paths: `rebuild/integration/apply_scarlet_host.py` settings row/switch flow; `rebuild/HostApp/ScarletSigningReadinessPanel.swift` explicit error taxonomy; regression tests `test_v48_r6p87_account_ui_cert_diagnostics.py`.
- Evidence status: Python source contract only until Mac Xcode27.2 CI verifies compile; on-device UI/p12/refresh unresolved. Preserve original V48 fullscreen/switcher, guest data and signing material.

### L146 · P88 native account rows UI (2026-11-16)
- User repeatedly shows active account row with a short trailing separator under `사용 중`, plus `추가 로그인` tint/row flicker on account switch. P85 nested Form cell + full-width Divider, P87 removed Divider but LEFT nested VStack and disabled-related tint changes. Neither is device-verified as a fix.
- P88 distinct structural strategy: `apply_scarlet_host.py` generates a native `ForEach` of Form **rows**, rather than a single `VStack` Form cell holding multiple accounts. Each native account row uses `.listRowSeparator(.hidden)` and stable content with no custom Divider. `추가 로그인` and inactive account controls use hit-test gating instead of `.disabled` dimming; `전환` label remains stable, no transient `ProgressView` replacement.
- P88 acceptance: on a signed device, switch A→B→A repeatedly; `사용 중` must have no short broken separator; `추가 로그인` label/tint and geometry must not flash; preserve V48 guest geometry, old data, account Team and cert material. Static tests cannot prove the visual effect.
- P88 scoped to Settings account UI only. Per-Team SideInstaller p12 import and `host_selected_team_mismatch` remain separate P0 defects, with no false completion claims.

### P89 · SideInstaller reference-native Account UI and per-Team p12 import (2026-11-17)
- Device P88 screenshot and current-launch log 2026-11-16 20:21Z: Settings title/email overlap on status bar; giant account row gaps despite P88 native Form rows; `host_selected_team_mismatch`, `archive_team_differs_from_signed_host`, certificate worker failure, active account switching itself verified.
- Direct upstream study: FrizzleM/SideInstaller `ios-app/SettingsView.swift` native `NavigationStack + Form`, `accountSection` with a plain `Button` per saved Apple ID and `accountRow` containing email+in-use caption; `ios-app/AccountStore.swift` selected account owns Team; `ios-app/CertManager.swift` `performImport` validates the P12 against the active account's Apple team before using it. SideStore pinned `Core/Certificates/CertificateManager.swift` provides `parse`, `setActiveCertificate`, `getAllLocalCertificates`, and Keychain storage. Reference: https://github.com/FrizzleM/SideInstaller (copyright FrizzleM, non-commercial reference; no official SideInstaller release repacked).
- Distinct source fix: Settings injected rows now plain `Button` per account with native Form cell sizing/no manual separator/insets; native inline navigation title and no forced hidden scroll edge on settings tab only. Do NOT add arbitrary safe-area insets or parent window reflows; preserve guest geometry.
- P12 native data path now `ScarletSigningReadinessPanel.importExportedP12` → `ScarletNativeSavedAccounts.importSelectedTeamCertificate` → on-device XPC `scarletImportInstallCertificate` → embedded SideStore `ScarletInstallTeamAuthority.importArchive` → `CertificateManager.parse`, selected Team OU and Apple portal serial check → `setActiveCertificate` and SideStore active-Team readback. Failure leaves unrelated team/host certificates untouched; never copy B P12 to `LCCertificateData`. XPC must never log or forward p12/password outside the device.
- Host A signed by Team A is NOT managed under Team B. Host bootstrap mismatch on B with no B apps must present `no_managed_apps_for_selected_team`, not falsely imply B's authenticated Team is unusable; B native-managed installed apps are independently selectable and refreshable. Never re-sign host A under Team B.
- Source regression suite: 855 tests passed with 3 infrastructure skips. Native Xcode 27.2 build and real iPhone A/B p12 + top UI **NOT YET VERIFIED**. Mandatory: test account A→B→A, P12 Team B import with portal serial, Team A remains unchanged, refresh B-only apps without host A. Audit exact P89 git diff in L148 before declaring build success.

### L149 · P90 Account+Team ownership (2026-11-17)
- User requirement: Apple ID A and Apple ID B MUST be independently owned identities, not a shared permission switch. Device P89 current launch `022f7fbc` (source `c667fa3cd4b1`) shows account switching verified and one selected-Team P12 import, but guest `certificate_invalid`/`signature_postcheck_invalid`, auto refresh selectedTeam no-app and manual refresh install-unverified. These remain unresolved, not CI successes.
- Original SideStore CoreData has `InstalledApp.team -> Team.account -> Account.appleID`, plus `Team.isActiveTeam` and `Account.isActiveAccount`; P68/P75/P89 only filtered by Team ID, which cannot distinguish two Apple IDs sharing a Developer Team. P90 instead pins both authenticated `AuthManager.currentAppleID` AND native active Team relationship under SideStore gate for IPA install, managed slots, refresh and original signed-host bootstrap.
- Native install callback must read back the same `InstalledApp.team.account.appleID` plus `Team.identifier` before claiming pipeline success. No cross-account activate/deactivate, auto-switch, app deletion, revocation, transfer, or rewriting signed host authority. Identity unavailable => fail closed. Existing signed Scarlet host stays with its original Team, even if B is selected.
- P90 code changes scoped to `ScarletGuestSavedAccounts.swift.txt`, `ScarletDeviceInstallAgent.swift.txt`, `ScarletGuestRefreshAgent.swift.txt`, tests and workflow only. P89 native account UI untouched; P89 SideStore per-Team P12 import untouched.
- P90 static acceptance uses two Apple IDs even when Developer Team is the same; static tests cannot substitute for iOS27.2 device signing, installed-app per-owner lists or user screenshot. Check A->B->A and app-slot, native install, per-owner refresh.

### L150 · P91 원본 SideStore CertificateManager 기반 게스트 서명 복구 (2026-11-17)

- 2026-11-17 08:29 KST P90 실기기 로그(빌드 3.8.90, SourceCommit `9a3ded62e0f1`, session `93bd3576`): `certificate_preflight`의 P12·서명호스트 팀 일치와 AppGroup 통과에도 실제 게스트 3회 `certificate_invalid` / `signature_postcheck_invalid`; A/B 전환 성공, 계정별 P12 가져오기 성공, 자동 갱신 선택 팀의 관리 앱 수는 0. 이는 수동 가져오기와 게스트 JIT-less 커널 서명 성공이 별개의 경로임을 입증한다.
- 원본 LC 소스 `LCUtils.validateJITLessSetup`은 시험용 dylib를 `ZSigner`로 서명한 후 커널 `checkCodeSignature`를 검사한다. 기존 P78 복구는 `com.SideStore.SideStore` 등의 레거시 generic Keychain `signingCertificate`만 조회하므로 P89가 추가한 원본 SideStore `CertificateManager`의 계정별 활성 P12에 도달하지 못한다. 기존 실패를 타이머·여백·재시도로 처리하지 않는다.
- P91은 기존 P78 후보가 없을 때에만 인증된 SideStore LiveProcess XPC `ScarletNativeCertificateTransport.retrieveSideStoreCertificate()`로 원본 CertificateManager의 **기존** 활성 P12를 조회한다. 저장된 Apple ID 목록은 이전과 이후 두 번 조회하며, **활성 계정 한 개** 및 **호스트 서명 Team에 속한 유일한 계정 한 개**일 때에만 진행한다. 두 Apple ID가 같은 Developer Team이면 자동 교체하지 않는다. 후보 P12가 현재 LC 인증서와 다르고 서명된 호스트 Team과 일치할 때에만 P78의 기존 백업/검증/롤백을 재사용한다. Apple 포털 새 발급, 타 계정 전환, App Group 키 임의 덮어쓰기, 기존 인증서 파기 없음.
- 변경 소스 `rebuild/HostApp/ScarletIntegratedHostView.swift`, `rebuild/Tests/test_v48_r6p91_native_owned_guest_signer.py`, `.github/workflows/scarlet-paired-engines-build.yml`. 정확한 파일·코드 전후 차이와 원격 Git commit SHA들은 append-only `scarlet_remediation_history_appendix.json`의 L150에 기록돼 있다. 기존 P90 계정별 설치 소유권과 UI, P89 인증서 가져오기, V48 화면·회전·멤버십 로직은 변경하지 않았다.
- 신규 소스 계약 테스트 4개 통과는 Xcode 컴파일이나 iPhone JIT-less 성공 증거가 아니다. P91은 빌드 3.8.91·독립 미서명 IPA로 CI를 돌려야 하며, 실기기에서 A→B→A 및 관리 앱 계정 격리, `native_owned_host_team_p12` 복구 시그널과 `signer_recovery_verified`, 실제 게스트 화면/커널 서명, 원본 인증서 미변경 또는 실패 시 롤백을 검증해야 한다. P90의 `no_managed_apps_for_selected_team`은 별도로 등록·소유권 경로 확인이 필요하다.


## 2026-11-17 P93 / L152 — real P92 signed-device JIT-less signature failure

- BASE/ROLLBACK: `176c5c52f962f94bbffe3a945b1cc79a9522c215` (P92). P93 functional source commit `2361b305f77bc145201c1316d11d0c8f72186c4d`. Detailed immutable before/after unified hunks in appendix L152, not inferred diff.
- Real signed phone P92 build `3.8.92`, session `a58887b2`, source `176c5c52f962`: certificate+password+Team/AppGroup accepted, `jitless_manual_probe_failure_classified code=2` twice, `signer_recovery_started` five times, no `signer_recovery_verified`. Account A/B switches verified; an Apple certificate was issued for second account, but guest JIT-less kernel check remained invalid. No proof that missing P12 is cause; no successful guest display.
- P93 genuinely DIFFERENT mechanism: embedded signed host `embedded.mobileprovision` `DeveloperCertificates` X509 DER byte-match to the candidate P12 identity plus `get-task-allow`. Do not use Team OU or Apple portal status alone as host trust proof. If profile cannot be read or no exact cert exists, fail closed and preserve original LC signer. If two saved Apple IDs share one Team, permit one active verified owner **only if** the returned P12 matches the signed host profile. Original P78 snapshot/restore and kernel `LCUtils.validateJITLessSetup` remain unchanged.
- Validation receipts: `python3 -m unittest discover -s rebuild/Tests -p 'test_*.py'` -> 874 tests OK, 3 skipped; `python3 rebuild/diagnostics/scarlet_no_repeat_gate.py --proposal /tmp/scarlet_p93_proposal.json` -> 151 attempts PASS before edit. Separate native Xcode, published IPA, kernel and real device remain distinct status items. P93 final `--repository-check` must pass before release.
- On signed P93 device interpret `jitless_host_profile_signer_readback`: `host_profile_certificate_matched` allows P78 reversible candidate trial; `candidate_not_in_host_profile` indicates a different host signer, so existing host must be re-signed with a matching profile/private key rather than importing unrelated team P12; `installed_profile_unreadable` means extraction inconclusive; `host_development_profile_required` means get-task-allow absent; `p12_identity_unreadable` means archive parse failed. No assumptions about actual device result until its newest current-run log.
- Do not modify V48 visual scale, rotation, Island, switcher, audio, account credentials, revoked certificates or signed app provisioning. Never call the test suite success a signed-device repair.


## 2026-11-17 P93 Xcode 27.2 compiler failure / L153

- Native CI run `44049432652` (source `eec534d0eeec`) failed before producing IPA. Downloaded build-log archive `14313920528` confirms `ScarletIntegratedHostView.swift:107:77: error: conditional downcast to CoreFoundation type 'SecIdentity' will always succeed` (Swift compiler exit 65). This is NOT proof of an invalid or revoked Apple signer.
- In `916bdf7639501a27fc4b81ffec20f80bd28dfd06`, replace the illegal `as? SecIdentity` (after successful `SecPKCS12Import`) with separately checked nonnil `identityObject` and explicit `as! SecIdentity`. The Security.framework successful result and required import item are the actual type contract; no certificate or key data is logged. Regression test added by `bab76c05bbe6c9eab6d128c8d4a5ed8c9bbe90b4`.
- Complete exact code diffs are in append-only `L153` along with immutable commit IDs. Earlier L152 records remain unchanged. Native Xcode success, IPA publication, real JIT-less kernel validation, guest rendering, and account A/B repair remain independent unverified checkpoints until evidence exists.
- After source corrections and before any conclusion, run `python3 rebuild/diagnostics/scarlet_no_repeat_gate.py --repository-check` and the full Python test suite; then verify latest GitHub Actions by exact HEAD, not an older successful artifact.


## 2026-11-17 P94 / L154 — imported Apple-ID-owned P12 never reaches LC guest signer

- Signed phone evidence: P93 `SourceCommit:9e7ccdffb8fa`, `Build:3.8.93`, `CurrentSession:885de5b8`. Guest `launch_requested` 09:55:54Z, `certificate_invalid`, `signature_postcheck_invalid` code2 09:55:56Z; `jitless_host_profile_signer_readback=p12_identity_unreadable`; `native_signer_recovery_blocked=host_account_owner_unverified`. Explicit user-owned P12 import `account_p12_imported=imported_selected_team` at 09:56:30Z, AFTER failed guest attempt; no post-import signed-device kernel test or launch. Pairing file missing for refresh: separate issue.
- P94 changes ACTUAL runtime path. `ScarletSigningReadinessPanel.importExportedP12` now accepts SideStore import success only for unchanged exactly-one active Apple ID + Team, then passes explicitly imported P12 and password into existing crash-safe P78 `ScarletGuestSignerRecovery.trialExistingSideStoreCertificate(nativeCandidate:)`; no cross-account automatic overwrites. Existing P78 checks installed host Team and P93 checks byte-identical signed `embedded.mobileprovision` X509 DER before touching LC AppGroup, then the original kernel `LCUtils.validateJITLessSetup` decides success vs exact restore/rollback.
- P94 replaces P93 ONLY certificate DER extraction from Apple's `SecPKCS12Import` with a public-certificate-only `ZSignAsset.InitSimple + i2d_X509` wrapper in pinned original `ZSign/zsign.mm`, exposed via `LCUtils`. This directly addresses P93 signed-device `p12_identity_unreadable` while original `LCUtils.getCertTeamId` ZSigner identified Team. No private key exported or logged.
- Real changed source commit `b8a61ab641f49a35fe77cb994266f1ddcd43fd47`; per-file full before/after hunks in append-only remediation appendix L154; rollback `9e7ccdffb8fa48233e698d96805593ed0c59f238`.
- P94 Python test suite `880 OK / 3 skipped` and pinned upstream DER injection fixture succeed; native Xcode27.2 archive, unsigned IPA publication and user signed guest success separate until verified. Never declare resolved from CI.
- On next device log distinguish `account_p12_guest_signer_trial_requested`, `signer_recovery_trial_started`, `signer_recovery_verified`, `signer_recovery_rolled_back`, `signer_recovery_blocked` reason, and `jitless_probe_finished`, post-import guest launch. If matching P12 is revoked/host-profiling inconsistent, fix actual signing provenance, not more cert retries. Preserve original V48 display/scale/audio/keyboard and A/B account ownership.


## 2026-11-17 P96 / L156 — Apple portal proof and installed-host signer truth

- Signed P95 device log `SourceCommit:9d930382bf1d`, `Build:3.8.95`, session `ae30a2fc`: twice `native_account_issue_result=ready_existing`, but `jitless_host_profile_signer_readback=candidate_not_in_host_profile` and `signature_postcheck_invalid` code2. `sidestore_managed_apps_inspected count=0 reason=no_managed_apps_for_selected_team` blocks APP refresh independently of P12. Account switch verified; later account import blocked, reason redacted, so do not claim which account failed until new visible safe category.
- Code cause: P95 `ensureSelectedTeamCertificate` fast-returns after local OU + X509 expiry `prepare`, before checking Apple's current Developer Portal serial list. It then says an existing valid certificate was reused even when the installed host profile rejects that signer. These are three different states: Apple-registered key, host-signed JIT-Less trust, managed app refresh eligibility.
- P96 functional strategy: explicit existing certificate button directly calls native account-owner-verified `issueInstallCertificate`, where `issue` fetches Apple portal certificate serials BEFORE reusing a cached P12, uses only an unexpired portal-listed serial and matching local private key, or creates a new Apple certificate without revoking existing ones; owner is rechecked across awaits. A successful per-account P12 import checks installed host profile exact X509 DER BEFORE attempting P78 reversible guest-signer recovery. It visibly reports a host re-sign requirement on mismatch, and stops a failed selected-account import before issuing a native provider success receipt. Never conflate `no_managed_apps_for_selected_team` with certificate expiry.
- Maintain V48 UI scale/status bar/Island/switcher/audio, unchanged original Apple IDs, P12 Keychains, bundle ID, and non-destructive updates. No Apple portal account issuance, host re-sign or real iPhone JIT-Less success is verified by Python or Xcode CI.
- New signed-device gates: `native_account_issue_result=ready_existing_portal` only after Apple portal serial match, or `ready_issued_apple` only after actual portal creation. If P12 fails `account_p12_guest_signer_blocked` with `candidate_not_in_host_profile`, re-sign installed host using its exact approved developer certificate/profile; never blindly swap another account's private key. Only `signer_recovery_verified` with kernel success followed by actual guest display can close the guest-launch issue.


## 2026-11-17 P97 / L157 — Apple ID-scoped certificate binding

- Signed-device P96 source commit `920732fe2da3`, build `3.8.96`, session `6fffed84`: current guest launch JIT-Less `signature_postcheck_invalid`, installed profile existing signer `candidate_not_in_host_profile`; target native refresh `no_managed_apps_for_selected_team`, and two selected accounts may share a Team ID with native global active P12. No sign of actual guest kernel success.
- Source root cause NOT merely a message: `ScarletInstallTeamAuthority.matchingCertificate(for:teamID)` chose the global current certificate or first locally stored cert matching Team OU; account A->B switch could inherit A's signer. Even after P96 Apple portal serial validation, the reused cert was not persistently bound to the selected Apple ID.
- P97 actual runtime repair: a new per-(Apple ID, Team ID) Keychain serial mapping, verified write/readback. Native account switch and readiness choose only that pinned serial; unpinned account no longer inherits a global active certificate. Explicit Apple portal-validated cert issue/import binds its serial to the unchanged selected Apple ID and restores chosen native active certificate without revoking any prior Apple certificate. XPC allows distinct owner/binding failure categories. V48 guest scale, Island, audio and UI unchanged.
- Device validation pending: A->B->A must preserve each account's serial/private key and target app ownership with actual installation, no cross-selected active cert; then native signed refresh must show registered managed apps, and host signer identity must match installed embedded profile for guest kernel validation. A saved or portal-listed certificate remains distinct from an installed host signing identity, and P97 does not automatically re-sign/reinstall the running host. Do NOT claim user-visible guest success from CI.
