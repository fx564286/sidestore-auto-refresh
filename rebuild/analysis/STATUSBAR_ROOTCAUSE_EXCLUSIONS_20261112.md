# Scarlet Crystal — unresolved top bar obstruction / root-cause exclusions
Date: 2026-11-12 KST. Baseline: R6P4 commit 341ef98d057bc8f82e665ba51dced94c638928b9 (CI passed).

## User-confirmed unresolved behavior
On iPhone iOS 27.2, guest titles/search or navigation controls can occupy the Dynamic Island region or become unreachable. Recorded host/remote owner Safe Area = 62pt does not prove visible guest layout. A temporary 62→0→62 readback has also appeared.

## Previously attempted approaches — NOT new solutions
- Host Safe Area, remote scene Safe Area, zero-inset guard, per-scene cache, periphery and status-bar layout metadata: R5, R6, R6P5. Still no demonstrated optical fix.
- Direct UIKit UIWindow/root view geometry inspection: R6P6; user reports that category has already been tested.
- Overlay hit interception, native outside-dismiss shield, window levels: explored and does not explain the top UI position by itself.
- Original LiveContainer presentation path and classic guest fallback: already examined.
- Frame scaling, padding, virtual-window resizing: unacceptable regression to guest geometry/touch behavior.

## Commit-level architecture boundaries
- V35 46284c0b2a1afbcbc3c1ee9dfecb7ec00d094ed1: classic/fullscreen fallback; no V45 compositor.
- V36 f5de15cc5f17d9a36d2a2969ee6b61c721add530: removes old LC dock renderer/decorated window chrome.
- V45 1c20f05dbf58d28c2493d958d4734bf74e6cba77: introduces persistent embedded AppSceneViewController/LiveProcess fullscreen scene stack.
- R6P4 341ef98d057bc8f82e665ba51dced94c638928b9: preserved resident architecture, audio and Home gating.

V35 to V45 consists of 13 commits. V36 and V45 are the main architectural rendering transitions in that sequence. This does NOT demonstrate which version first caused the actual on-device problem.

## R6P7 different investigation: launch-time bundle metadata
In the pinned original LiveContainer LCBootstrap.m, the runtime replaces the process main NSBundle and CFBundle with the guest bundle before invoking the guest main() function. R6P7 records BEFORE and AFTER effective guest/host launch policy keys:
UIStatusBarHidden, UIViewControllerBasedStatusBarAppearance, UIApplicationSceneManifest (presence), UIRequiresFullScreen, and UISupportedInterfaceOrientations count.

This does not change UIKit, Safe Area, guest views, frames, scales, overlays, or signing profiles. Only anonymous boolean/count values, ephemeral PID and stage are relayed through the existing App Group into the same diagnostic viewer.

## Next-step decision gates
- If effective NSBundle/CFBundle declaration differs from the guest bundle: isolate process launch identity/timing and scene policy registration, not view geometry.
- If declarations match: exclude this axis and perform controlled regression bisection of the V36/V45 rendering ownership changes.
- If no diagnostic: report precisely whether original bootloader or App Group storage failed. Never call the absent data a success.
- Passing CI/Xcode does not establish visible or touchable top controls on iPhone. Signed device test remains required.

## Source references
V35–V45: https://github.com/fx564286/sidestore-auto-refresh/compare/46284c0b2a1afbcbc3c1ee9dfecb7ec00d094ed1...1c20f05dbf58d28c2493d958d4734bf74e6cba77
R6P4: https://github.com/fx564286/sidestore-auto-refresh/commit/341ef98d057bc8f82e665ba51dced94c638928b9
R6P7 PR: https://github.com/fx564286/sidestore-auto-refresh/pull/100
