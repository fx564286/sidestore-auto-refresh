# Scarlet Crystal P69 — Settings UI ownership cleanup

## Evidence and scope
- Real signed P68 CURRENT RUN `cb9cabf6` build `3.8.68`, source `f6dae87d7943`: saved auth and pairing restored; certificate worker failed with code `0` then existing same certificate observed. Background refresh was deferred (retry interval), not proved failed or successful. iOS native status bar was still hidden. No A/B team install proof was present.
- User requested removing duplicated actions and persistent passive labels. Primary problem is duplicate *presentation*, not evidence of repeated SideStore execution. No change to native TeamOperationGate, AppManager, PKCS12 or encrypted auth data.

## Changed visible controls
- Account settings: one login state, `추가 로그인` when authenticated. Removed duplicate `서명 준비됨 / 서명 확인 필요` caption.
- Signing/pairing: removed always-on `자동 갱신`, `자동 갱신 대상`, `이 앱 자동 갱신`, `서명 상태`, and extra `갱신 문제` label. Show only `최근 갱신` when a real attempt exists; keep one actionable error and native `지금 갱신`, `SideStore 인증서 받기`, `P12 파일 선택` and pairing.
- Apple account selection: removed long persisted-session explanation; show certificate warning only for selected team missing a signing P12, not a repeated `인증서 저장됨` success line.
- Device app manager: removed stale false warning that adding accounts can never change installation team. Retained real SideStore active/inactive app controls.
- Experimental resident toggle and source download panel: removed duplicate explanatory captions; kept actual controls, cancel, and progress.
- Preserved versioned V48 behavior, original Scarlet UI palette and no code changes to guest rendering, certificate private keys or SideStore installation pipeline.

## Verification status
- `python3 -m unittest discover -s rebuild/Tests -p 'test_*.py' -q`: 758 tested; 755 pass + 3 skip.
- GitHub YAML parser passed; Python integration script syntax passed; `git diff --check` passed.
- Native iOS Xcode, unsigned IPA release and signed iPhone UI/device checks are separate verification gates, **not claimed passed here**.
- Exact file-level before/after diffs in L118 of `rebuild/diagnostics/scarlet_remediation_history.json`.
