# Scarlet Crystal — Upstream-Parity Recovery / Design Freeze
Date: 2026-11-04 | Base: `fix/scarlet-v181-figma-design-auth80045-20261103`
Status: AUDIT/WORK ORDER ONLY. No IPA, device fix, Figma parity, or subagent execution is claimed.

## Immutable product contract

Scarlet Crystal is a LiveContainer + SideStore **fork**, not a new app or a stock UI replacement. Keep the latest coherent upstream semantics and every working Scarlet feature; never downgrade to a historical binary merely because a new one fails.

**HARD STOP / ZERO-TOUCH: the user-authored Liquid Glass implementation is frozen.** Do not edit its Swift/ObjC source blocks, optics, tints, blur, shadows, elasticity, morph transitions, press tracking, gestures, appearance toggles, or rendered assets. Do not replace it with a replica. Record baseline source spans and SHA-256 before touching nearby files. Any necessary work in a shared file must avoid the frozen spans; independent reviewer checks the diff.

Figma is the authority for the remaining custom design. Never infer or select colors, palette, shadows, spacing, radii, typography or animation from aesthetic preference or a generic system default. Work on Figma-linked changes only after identifying the *real* existing file/node/revision, extracting actual values, and comparing them to output. Do not create a substitute Figma file and call it the original. No visual feature is allowed to silently fall back to stock UI.

Preserve the installed bundle identity and extension IDs, signed entitlements, profiles, Keychain, pairing, JIT-Less state, installed guest IPAs/containers, personal preferences and source database. No uninstall, forced credential wipe, certificate replacement, unapproved portal writes, or guest-data migration. Never log passwords, 2FA answers, tokens or private pairing bytes.

## First-pass upstream chronology (not an exhaustive issue inventory)

- LiveContainer 3.4.0: NSBundle path regression (#409), signing compatibility fixes; 3.5.0: multitask windows, launcher/dyld/runtime improvements, multiwindow / input ownership; 3.5.1: Liquid Glass preference behavior changed, **not authorization to alter Scarlet Glass**.
- LiveContainer 3.6.0: UserDefaults hook refactor, black screens (#543/#594), app switching, keyboard fixes; 3.7.0: iOS 26/27 launch + JIT and status-bar/window controls; 3.8.0: improved multitask keyboard (#1402/#844/#870), crash sheets, app storage, signing, networking. Nightly 2026-10-17 `9108ae6` fixes #1644, #1655, #1666.
- SideStore 0.5.10: source-update repair; 0.6.0: broken refresh and data migration, **not a suitable regression fallback**; 0.6.1/0.6.2: migrations, certificate export and refresh improvements. 0.6.4: Apple-side sign-in breakage; 0.7.0-alpha (2026-09-11) fixes a 503 case. Nightly 2026-10-27 `cd260851` is experimental; `-80045` remains reported.
- Current product must separately verify the exact embedded SideStore gitlink `ee3cc16`, SideSign `752d1ef` and LiveContainer `9108ae6`: displaying LiveContainer 3.8.11 alone does not prove the integrated SideStore matches an official current nightly.

Reference releases: https://github.com/LiveContainer/LiveContainer/releases and https://github.com/SideStore/SideStore/releases
Issue references: https://github.com/LiveContainer/LiveContainer/issues/1688 ; https://github.com/LiveContainer/LiveContainer/issues/1595 ; https://github.com/LiveContainer/LiveContainer/issues/1676 ; https://github.com/SideStore/SideStore/issues/1647 ; https://github.com/SideStore/SideStore/issues/1665

## Source and device findings (facts vs hypotheses)

**Proven from GitHub source and reports**
1. `docs/SCARLET_DESIGN_BASELINE.md` says V179 compiled current parents but FAILED all eight user-UI contract checks. This is a recorded missed forward-port, not a hypothetical design concern.
2. V177 -> V181 contains 84 commits; V180 -> V181 contains 59. The user repo's default main and V181 are divergent. Audit the V181 candidate branch, never assume default/main or patch by version-number alone.
3. `scripts/verify_scarlet_design.py` checks `SCARLET_V*` marker presence, **not** Figma fills/variables/screen pixels. It may report `can_publish_as_design_preserved=true` with `runtime_design_verified=false`; `.github/workflows/scarlet-v181-design-auth-build.yml` labels an artifact `fully UI-verified` even though it runs no physical visual-parity gate. Correct that false reporting; do not equate code-marker presence with Figma parity.
4. V181 `patch_v181_auth80045.py` conditionally adapts default UA for Windows/Android Anisette profile and improves error text; it does **not** itself repair service startup or establish Apple sign-in/2FA success.
5. The source's `V3AuthStore.cancel()` invokes `authCancel`, then `await oldTask?.value`, then `reconcile(force:true)`. Cancellation cannot be considered complete just because the UI updated; investigate bounded settlement, late replies and terminal ownership with the real service.
6. NRG's upstream integration `docs/APP_IMPLEMENTATION_PARITY_AUDIT.md` identifies further headless adapters that changed the meaning of upstream callbacks: extension selection, settings defaults, virtual-window close, sign-in `resolveResign`, backup, cached settings, and signing readiness. Carry tests for these contracts into Scarlet instead of ignoring the earlier research. `README.md` explicitly warns that its v3.1.0 is not a device-verified stable authentication release.

**Proven from user-supplied iOS 2026-11-04 log**
- `LiveProcess` process PID 21770 launches around 03:25:40, loads SideStoreSupport and SideStore, logs `app_group_resolved=0`, loses XPC and exits with SIGABRT(6). The log does **not** contain the exception backtrace; the exact abort function is unproven.
- SwiftUI reports off-main-thread published-state fault; UIKit reports invalid UIScreen cross-screen coordinate-space conversion. These are separate defects to audit; neither independently proves the cause of the extension abort.
- `Cancelling...` persisted in the user's UI; correlate with the service lifecycle and cancellation ownership, not just Apple `-80045`.

**Hypotheses requiring evidence**
- Missing effective signed App Group entitlement, invalid effective shared-container resolution, guest bootstrap identity conflict, a Core Data duplicate-store setup or class/swizzle initialization race may cause the SIGABRT. Compare exact installed entitlements and crash `.ips` if available; never claim one is proven just from `app_group_resolved=0`.
- LiveContainer #1688 reported a related integrated SideStore 3.8.11 launch failure with `Can't add the same store twice`. It was closed; different error until a matching exception is obtained. Use it as an investigation lead, not a confirmed duplicate.

## Main agent + independent workstreams

**Coordinator (MAIN)**: owns dependency graph, V181 base SHA, issue-to-file map, API compatibility, integration boundaries, CI reproducibility, merge/no-merge decision, and signed-device acceptance log. Admit each component patch once; prohibit blanket overwrites, old-version source grafting, unrelated beautification, duplicated Direct/LiveProcess overlays or auth retries.

**A1 Upstream archaeology — graphify, review-agent (READ ONLY)**
- Collect every LiveContainer and SideStore issue/PR/release since project inception (pages/cursors; include open/closed and close/merge SHA); deduplicate by root cause and feature; identify original fix + successor/regression + current-pin reachability; map symbols/files. Emit `reports/upstream_issue_lineage.{md,json}`, source references and missing/overridden patch inventory.
- Confirm the provenance of `LiveContainer/SideStore` vs `SideStore/SideStore`, nested SideSign/minimuxer, and the exact signed IPA tree.

**A2 LiveProcess / bootstrap — systematic-debugging, test-driven-development**
- Own `LCBootstrap`, `LiveProcess`, `SideStoreSupport`, app group runtime and XPC-ready handshake. Trace process startup with stage-specific non-sensitive structured markers and same-attempt correlation. Distinguish signed-entitlement issue, invalid group, duplicate persistent store, ObjC exception, and loader failure. Fix the first proven violation only. Test extension actual post-sign launch, XPC peer admission, service-ready after cold start; no broad rewrite.

**A3 SideStore auth/refresh — systematic-debugging, test-driven-development**
- Own headless auth/session, `authCancel` and `await oldTask?.value` liveness, per-session one-shot completion, response races, non-destructive reauthentication, Anisette identity and `-80045` classification, provisioning/team/account, source persistence and refresh. Simulated negative tests for service loss, user cancel, late reply, 503, -80045, 2FA. Real device success is separate from unit tests.

**A4 LC guest runtime / layout — graphify, systematic-debugging**
- Own rotation/safe area/fullscreen/keyboard/video viewport, Direct/LiveProcess one owner and no duplicate controls, and background/foreground state. Follow upstream corrected screen/scene coordinate rules and run iPhone portrait-landscape-portrait tests. **Do not touch Liquid Glass code** or alter Figma visual tokens.

**A5 Figma fidelity — Figma read-only, visual QA**
- First recover the existing user's Figma design file key / relevant exact node IDs (none confirmed in repo audit); never invent a substitute. Export fills (sRGB/opacity), strokes, variables/modes, gradients, shadows, radius, size, typography, spacing and screenshots. Commit a provenance-locked comparison manifest (file/node/revision/hashes), not a guessed palette. Compare every UI change in normal/dark/portrait/landscape and gesture states. Use screenshot difference and measurable token checks, with native blur/antialias masks separated from strict static-color comparison. Report each mismatch rather than silently adjusting it. Liquid Glass itself remains frozen and is observed for regression only.

**A6 Signing/installer/parity — verification-before-completion**
- Verify every expected actual nested extension, signed App Groups, Keychain groups, four profiles where configured, team and unique entitlements, and in-place upgrade identity. Compare unsigned vs **post-sign installed** binary and effective data-container access; never erase identity or material. Keep the Arch installer and live log export compatible and non-destructive.

**A7 Independent reviewer — review-agent (READ ONLY)**
- Review every PR defect-first, compare against both upstream owner contracts and frozen design source hashes. Reject changes without targeted before/after tests, unrelated edits, unfinished error handling, implicit retries, incomplete secrets redaction, no-device-proof claims, or any Liquid Glass diff.

Use isolated git worktrees and one writer per owned file; parallelize source archeology, baseline recovery, auth simulation, UI capture, and signing audit. Require review after patches integrate. If Codex subagent/remote Linux tools are inaccessible, keep work orders queued: do **not** claim agents are currently running.

## Ordered execution, hard gates and evidence

G0 — Freeze: capture exact source commit, signed installed IPA metadata, effective entitlements, current Figma baseline (if accessible), hashes of Glass source spans and screenshots. Keep all old branches/artifacts/data. Block product release until Figma is identifiable and direct device QA passes.

G1 — Root-cause: reproduce `LiveProcess` SIGABRT with service/app-group/launch journal; obtain first exception/stack when available, or honestly report unknown. Fix and retest `LiveProcess` cold start, connected service, authenticated snapshot. No `-80045` work substitutes for this gate.

G2 — Authentication: real account prompt → 2FA → account persistence → team/profile readiness; user cancel → authoritative backend terminal state or bounded unknown-safe recovery; no permanent `Cancelling...`, no false `Signed in`. Preserve all secrets and account.

G3 — Parity: run upstream fix lineage checklist and regression suite for app import, extension prompt, sources, launch, container preferences, JIT/guest return, refresh, backup, protected data. Missing elements are restored from owner contracts, not old stock UI.

G4 — UI geometry: preserve Glass SHA and user-authored tabs/buttons; first-tap outside dismissal, same recent/window panel widths/heights, unclipped long-press, single route, no scroll, safe-area/notch touch, portrait/landscape/maximize/video. Record phone screen capture before and after.

G5 — Figma fidelity: exact token mapping and screenshots, including colors. No original Figma file = `BLOCKED_VISUAL_PARITY`, **never** `UI_VERIFIED`. Markers-only checks are `SOURCE_MARKERS_ONLY`.

G6 — Product CI: pass source tests, Swift native build, signed IPA audit, install upgrade preservation, and physical-device acceptance. Separately record not-tested tasks. Never infer iPhone success from macOS CI or an unsigned IPA.

G7 — Release: only after G0–G6, signed and exact source commit/IPA SHA is accepted on user device, publish a new forward version (no downgrades). Failure preserves the previous installed app unchanged and produces attributable evidence.

## Immediate first PRs to create after owner review

- PR-A: nonfunctional instrumentation for LiveProcess/App Group/XPC crash boundary + precise extension SIGABRT cause, **without edits to Liquid Glass**.
- PR-B: bounded auth cancellation/terminal-state liveness + service disconnect test, without credential/pairing resets.
- PR-C: accurate CI reporting: marker-only is not design verified; distinguish real Figma pixel/token and on-device evidence, preserve existing artifact naming compatibility if installer depends on it.
- PR-D: preserve/repair verified upstream runtime and settings contracts, with source-fix-to-test traceability.
- PR-E: screenshot/geometry and Figma exact visual parity after access to the actual original node; Glass source frozen.

### Source links

- Current V181 candidate branch: https://github.com/fx564286/sidestore-auto-refresh/tree/fix/scarlet-v181-figma-design-auth80045-20261103
- Upstream LiveContainer: https://github.com/LiveContainer/LiveContainer/releases
- Upstream SideStore: https://github.com/SideStore/SideStore/releases
- Original integrated audit: https://github.com/NRG-Wardog/sidestore-auto-refresh/blob/main/docs/APP_IMPLEMENTATION_PARITY_AUDIT.md
- Auth cancellation source: https://github.com/NRG-Wardog/sidestore-auto-refresh/blob/main/scripts/templates/v3_unified_shell.swift

This file is a preliminary verified issue/workstream map; it does not represent complete ingestion of every historical issue, real agent execution, code repair, compiled IPA or Figma node inspection.
