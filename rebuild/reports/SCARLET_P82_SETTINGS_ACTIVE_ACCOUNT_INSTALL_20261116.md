# P82 / L137 — IPA 설치의 중복 계정 선택 제거

- P81 source baseline: `c5ad675b12d1` (iPhone session `e5f30ba9`, user attached 2026-11-16).
- P82 code commit: `2039f9b71c09ad7789c36328f4164fffcb7b9909`.
- Reported/observed: user already selected Apple ID in Settings; `serviceInstallIPA` produces `install_team_picker_requested` twice (seq162 and seq164) on iPhone. Original `ScarletIntegratedHostView.swift` force-opened P68 picker on each tap.

## Native code changes

1. **Settings is the only Apple account selection owner:** remove `ScarletInstallTeamPicker` and its redundant account activation and certificate-issuance buttons. Do not add a new Settings button.
2. Device IPA tap: `ScarletNativeSavedAccounts.list()` XPC readback -> require 1 active Apple ID -> `prepareInstallTeam(active.teamID)` native validation -> second account readback -> only then open system Files picker.
3. Capture both account ID and Team ID without logging either. Before original `ScarletDeviceInstaller.install` after staged IPA copy, verify that exactly the same account/team remains active. Reject any mismatch. No automatic team switch, account deletion or certificate revocation.
4. Retain original P68 certificate-to-team guard, native AppManager device installation, P70 inline Settings Apple ID switch and independent LiveContainer guest IPA installation. No guest UI/geometry/audio/keyboard or other signing code changed.
5. CI branch `fix/scarlet-v48-r6p82-settings-active-install-20261116`; separate host CFBundleVersion `3.8.82`, same host bundle identifier and short version `3.8.11`. Release target `scarlet-v48-r6p82-account-install-unsigned-20261116`, asset `Scarlet-Crystal-V48-R6P82-ACCOUNT-INSTALL-UNSIGNED.ipa` (unsigned; do not install without signing).

## Verification gates

- `python3 -m unittest discover -s rebuild/Tests -p 'test_*.py'` — 815 total, OK (skipped=3), from local source after P82 modifications.
- `scarlet_no_repeat_gate.py --proposal /tmp/scarlet-p82-proposal.json` — pass against all 136 previous attempts before edit.
- YAML parsed with Python PyYAML — pass.
- Xcode 27.2 native compile, CI ZIP and release asset, signed-device confirmation — **not yet verified**; presence of source or Python tests alone does not prove installation succeeds.

### Required signed iPhone scenarios

| Scenario | Expected result |
|---|---|
| Active Settings Apple ID A -> IPA 설치 | No duplicate Apple ID sheet; native preflight then Files; team A pinned |
| Switch to B in Settings -> IPA 설치 | Native preflight of B, no second picker; team B pinned |
| No active account / XPC unreadable | Files not opened; explicit account selection message, no installation |
| Active team certificate unavailable | Block with Settings certificate instruction; no implicit issue/revoke |
| Switch A to B during native preflight or while Files is open | Abort on readback mismatch, without installing under either stale team |
| Guest IPA import / dynamic island / statusbar / keyboard / audio | Regression unaffected by source edit; must be checked separately on signed device |

**No-repeat evidence:** prior L116 P68 introduced installation-only selection; L119 P70 made Settings account switch visible; P82 removes the second owner rather than adding another team switcher. Exact before/after diffs for all six changed source/test/CI files and source SHA are in `scarlet_remediation_history.json` L137 and will be included in subsequent in-app exported logs.
