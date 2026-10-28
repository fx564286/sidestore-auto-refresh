# Scarlet Crystal V154 — runtime-only remediation work order

**Status: OPEN / not fixed. Do not report resolved until iPhone interaction is proven.**

## Baseline, invariants, and owner

- Baseline: V153 `3.8.226`, commit `80bbeda9b969646d24fbca310c3227f749e7e79d`. Previous GitHub CI #40769773867 was successful and uploaded an unsigned IPA; the user reports **all three runtime defects still exist**.
- Source: `scripts/patch_v153_three_fixes.py` with generated `MultitaskSupport/MultitaskDockView.swift` and `LiveContainerSwiftUI/Views/V3UnifiedShell.swift`, plus Direct `LiveContainer/LCBootstrap.m`.
- Create a separate code branch from V153. **Do not edit or cancel V153 run / IPA.**
- Freeze as golden: top `최근 실행 앱 / 창 관리` segmented tabs, their rounded layout and animation, entire outside frame and glass texture of `창 관리` panel, existing window action buttons, App IDs, bundle identifiers, signing, guest viewport fixes and working LiveProcess mode.
- **Only 3 tasks** below. Do not add a second Direct button, extra panel/window, window-close button inside the panel, guest-specific workarounds, or new unrelated features.
- Use separate defect-review, implementation, and QA responsibilities. Code-marker `grep` and unit tests are not substitutes for real device interaction.

## BUG A (P1): recent app row glass clips when long-pressed

**Repro:** LiveContainer/guest → open picker → `최근 실행 앱` → long-press an Instagram row or any other guest app. Native glass bloom is cropped/overbright; top segmented tabs do not show this bug. Reproduce with first/last row, one/multiple rows, light/dark background, portrait/landscape.

**Trace:** inspect native `UIButton.Configuration.clearGlass()`, row container, scroll view, `UIStackView`, `UIVisualEffectView` and *all ancestor* `clipsToBounds`/`masksToBounds`, view/layer transform, layout margins, hit-test rect and native optical effect padding. V153 already removed the row's custom `SCGlassControlPress` and set `scroll.clipsToBounds = windowActions || directMode` yet did not solve the defect; do NOT repeat that same patch and claim fixed. Determine exact clipping ancestor or optical surface overflow using real screenshots or on-device view hierarchy. Keep the capsule look and natural long-press effect, but no cut-off text, bloom, or asymmetry.

**Acceptance:** actual iPhone before/after capture; 10 repeated press/release cycles on first/last recent app; no clipping. Existing top tabs/window actions remain pixel/layout-equivalent within intended animation variation.

## BUG B (P1): tapping outside the panel does not dismiss

**Repro:** open either `최근 실행 앱` or `창 관리`; tap video/background once outside the rounded glass panel. The panel stays open even though the footer says it should close.

**Trace:** `SCOutsideTouchDownRecognizer.touchesBegan`, `SCOutsideGlassTapObserver.install`, `refreshWindows`, `gestureRecognizer(_:shouldReceive:)`, `outsidePanel`, `outsideTouch`, `collapse` and animation completion. Trace on both owner and guest `UIWindow`/scene, including `SCGuestMorphWindow.hitTest` and the overlay's `UIControl` hit-test. Record structured *non-sensitive* runtime fields: stage, same-scene or cross-scene, touch-began/rejected reason, screen coordinate, panel bounds, chosen hit-test view class, callback and close completion. Include screen recording from actual device; do NOT record video image contents or credentials. Check overlay z-order, whether `material` itself consumes background events, .began vs .ended, `panel.window === owner` guard and gesture cleanup. Close exactly once without stealing inside-row or selected-tab touches.

**Acceptance:** one outside tap dismisses on both tabs; 10 repeated open/dismiss cycles, including across guest windows. Tapping within the panel triggers only its selected control. No duplicate recognizer, dead button, or extra panel-close button. The `앱 닫기` action remains for ending the guest, not dismissing the panel.

## BUG C (P1): Direct-mode existing right button is visually present but tap does nothing

**Repro:** start any Direct guest. Tap the *existing single* right floating ellipsis/guest-switch button; no recent-app panel visible. Try while paused/playing media, after a drag, after returning to the app, and on first launch.

**Trace the COMPLETE route (do not substitute an invoked log for an onscreen panel):**
1. `LCBootstrap.m`: handle's `UIControlEventTouchUpInside`, `SCGuestMorphPresenter.openShared` / gesture cancel and hit-testing in `SCGuestMorphWindow.hitTest`.
2. In Direct process: `SCUnifiedGuestUIBridge.presentFrom:sourceView:` availability, `MultitaskDockManager` fallback availability, URL scheme `scarletcrystal251://nrg-guest-controls` openURL result.
3. In host: `V3UnifiedShell.dispatchURL` delivery, `UIWindowScene` selection, correct source window/anchor and visible root view. Verify `nrgV112PresentDirectGuestUI` and `nrgV72PresentGuestSwitcher` presentation guards, overlay attachment and frontmost visibility.
4. V153 increased async handoff attempts and changed to Direct entry point, but user reports no effect. Reject confusing `method invoked`/`URL accepted` with `panel.visible=1`. Instrument each failure guard with a distinct code and avoid infinite retry/poll.
5. Only one existing host-owned picker and one floating Direct button; preserve original drag and LiveProcess behavior.

**Acceptance:** 1 tap → original shared panel visibly presented in Direct on-device; 10 repeated taps/open/close attempts, after drag, orientation change and guest foreground/background. Direct vs LiveProcess behavior preserved; no other button/window created.

## Test-first workflow / no false success

1. Start with **review-agent** defect-first review of V153 diff and actual generated sources, then run the user's preferred code/test agents for isolated diagnosis, implementation and independent review. Read project AGENTS.md and preserve upstream build order.
2. Reproduction evidence for EACH bug is required before code changes. If iPhone device automation is unavailable, add concise diagnostic logging and stop at *diagnostic candidate*, not `FIXED`; request/collect device logs.
3. Add tests that **fail on V153** and pass with the exact fix; test hit-testing, touch routing/collapse, Press geometry, Direct host presentation state, cache/invalidation and rapid reopening. Keep prior V58/geometry, Glass, signing and IPA tests.
4. Run Github fast preflight + full Xcode/IPA CI. Publish a new version **only after** source, packaging and workflow checks pass; do not overwrite V153. Keep full release gate and artifact checksums.
5. Deliver evidence: before/after recording/screenshots, current `stage=... reason=...` logs, minimal source diff, tests failed-before/passed-after, CI URL/artifact checksum, and **device acceptance** per A/B/C. Build-only success is NOT issue resolution.

**Hard release gate:** all three real iPhone scenarios must pass; otherwise leave this work order OPEN with failing scenario and exact next hypothesis.
