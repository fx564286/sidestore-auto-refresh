# Scarlet Crystal V73 — Apple-style movable guest control

## User requirement

The fixed top-right (1 o'clock) overflow covers Instagram and other guest apps' navigation/search/action buttons. Preserve Apple-like native styling and stop intercepting touches in that position. The control must not require a Dynamic Island Widget or an additional App ID.

## Applied changes

- **No fixed top-right constraint.** The existing `DecoratedAppSceneViewController` window control is now a movable, edge-snapping, 44 × 44 pt UIKit control. Initial position: **left side, below vertical center**; never upper-right.
- Native `UIVisualEffectView` with `UIBlurEffectStyleSystemThinMaterial`, dynamic system label tint and SF Symbol `ellipsis` instead of a custom opaque black overlay. Accessibility label/hint describe available gestures.
- Tap: original `UIMenu` with Minimize, Maximize / Restore, Close. Hold 0.55 seconds: V72 recent guest action sheet. Drag: move the control, then spring-snap to left/right edge.
- Clamps Y position to the controller/window's current safe-area insets, with explicit bounds for iPhone portrait and landscape. Saves normalized Y and chosen edge **separately for each orientation** in `lcUserDefaults`. No guest App Info or preferences are rewritten.
- Adds a gesture only to the control, **not the guest view/window or system status area**. The rest of the guest content remains touchable; the selected control position still occupies 44 × 44 pt and can be moved again as needed.
- Preserves V70 full-screen portrait safe-area fix, landscape behavior, V72 no-Widget/no-Activity policy (host + LiveProcess + ShareExtension = three installable app IDs), keychain/Team, JIT and original guest data.

The design uses iOS standard material/controls, aligns with Apple Human Interface Guidelines on safe areas, system materials and ≥44 pt interactive targets. The final appearance and gesture arbitration **still require a physical iPhone test**; passing source tests is not a runtime success claim.

## Acceptance tests

1. In Instagram/X/KakaoTalk guest, top-right in-app navigation buttons work without a fixed NRG overlap.
2. Native-looking control first appears at left center and drags to either edge. Verify constraints, stored placement, rotation, safe areas and windowed/maximized transitions.
3. Tap original window menu; hold for recent-guest switcher; pan cancels menu activation instead of causing accidental guest switching.
4. No notch overlay/Live Activity or LiveWidget extension in IPA; same original host Bundle ID, JIT/signing features, and no dropped guest state.
