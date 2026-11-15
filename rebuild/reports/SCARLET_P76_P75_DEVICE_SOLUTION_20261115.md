# Scarlet Crystal P76 — P75 서명 iPhone 실기기 실패에 대한 런타임 수정

## 입력 근거: 사용자 첨부 2026-11-15 09:38:19 UTC
- Signed Scarlet 3.8.75 SourceCommit `d551e0996dfb`, iOS 27.2, current session `30b0a2ea`, guest PID1226, safeTop62pt.
- P60/P63 native scroll viewport reflow `guest_owner_content_reflow_staged` → `guest_owner_content_reflow_reverted`. Native header retained, unsafe controls 8→6, late first control/windowY50. P74 2850/3550 samples `severe_nodes=2`, `near_controls=6`, `first_near_control_y=50`, `scan_complete=true`. Status clock/battery withheld (`status_hidden=true`).
- `automatic_managed_apps_inspected count=0 reason=no_managed_apps_for_selected_team`; valid RSD pairing. P73 source may fail to resolve real host path using only process argv[0]; selected-team mismatch must also be distinguished and never force re-sign host with team B.

## Executable source changes
1. Guest P76 scoped native post-header content origin. Only AFTER verified 2-pass native header, with previous P60/P63 body reverted, collect 4..12 real visible residual control nodes around y42..55 for 62pt safeTop, locate their single common full-screen native scroll (not guessed root or small carousel), verify original native inset/offset at stable top, and apply exactly the measured 9..22pt shift to both `scroll.contentInset.top` and `scroll.contentOffset.y`. Frame, content size, guest root, overlay, guest scale and touch hit testing unchanged. Verify after 180/560ms using actual control positions + complete P74 severe-media scan; if fail, reverse inset change while preserving current user scroll content position.
2. Host P74 pair-of-samples statusbar gate permits a strictly stronger `near_controls=0, severe_nodes=0, scan_complete=true` after actual verified header, while retaining the existing 2-sample precondition, strict PID and landscape guards. Existing near-boundary logic remains.
3. P73 SideStore host bootstrap tries actual loaded SideStoreSupport class bundle and verified `LiveProcess.appex` ancestor as alternate to process argv; signer/team/cert/provisioning/AppGroup checks and original CacheAppOperation+InstalledApp registration remain unchanged. Distinguishes valid multi-Team B from failed host discovery, no automatic re-sign across teams. Host allowlisted reasons and native refresh guidance updated in existing place, no new UI labels.
4. New P76 isolated integration tests, P73 outdated argv-only expectation updated. Preserve all prior remediation history, branch version 3.8.76 and signed profile requirement. Native Xcode CI + signed iPhone still required for completion.

## Required real-device proof
- Same guest PID: `guest_owner_layout_contract_retained`, then `guest_owner_content_reflow_first_pass` and `_retained` with result reason `p76_post_header_content_origin_native_safe` (no `_reverted`), P74 `guest_post_header_statusband_probe` severe_nodes0 on both 2850/3550, then `resident_native_status_band_readback.status_hidden=false` and visible clock/battery. No loss of scroll, touches, landscape or home/reentry.
- Same Apple A/B account: retained actual host bundle/Profile Team matches selected account A; SideStore `automatic_managed_apps_inspected` count>=1 for A, and Team B cannot re-sign A host. Distinguish any actual P76 host bootstrap error from no-managed case. Only real AppManager successful installation and signed device readback prove renewal, not CI.

## Constraints
- No additional App IDs, no uninstall, credential removal, SideInstaller cert revocation, profile rewrite, guest resizing, masking, clipping, source/theme change or spurious persistent status labels.
- Python unit/static assertions are NOT real runtime success. CI Xcode binary and signed iPhone outcomes must be reported separately.
