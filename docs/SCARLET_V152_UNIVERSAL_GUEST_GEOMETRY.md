# Scarlet Crystal V152 — Universal Guest Viewport Contract

## Scope
X, Instagram and KakaoTalk are examples, NOT an app allowlist. V152 retains
V151 shared DecoratedAppSceneViewController geometry and applies common checks
to all hosted guest windows. Do not branch on app name or hard-coded bundle ID.

## Shared requirements
1. Cold launch: one window-derived viewport; apply safe insets once.
2. Foreground return: reconcile retained guest without reconstructing it.
3. Rotation: support portrait/landscape, host/guest mismatch and iPad.
4. Fullscreen/windowed: preserve user mode and correct scene bounds.
5. Touch parity: rendered frame and interactive frame must stay aligned.
6. Preserve OS-controlled Dynamic Island, status-bar and home gesture areas.
7. Do not delete per-guest TouchSafe preferences to force identical UI.
8. Preserve existing Liquid Glass, app switching, code-signing and App IDs.

## V151 CI failure
Run 40710117266 stopped at the historical V58 fullscreen audit before Xcode
compilation. It required the removed V139 maximized host-orientation frame
assignment. V151 now serializes dimensions using the actual guest orientation.
V152 recognizes ONLY the complete V151 successor with all three new markers
and continues to reject incomplete V139/V151 implementations.

## QA acceptance
Source tests span eight screen rectangles, both host orientation values,
both guest orientation values and maximized guest scene diagnostics.
Physical QA must still separately cover portrait-only, landscape-media,
text-entry, navigation-heavy, camera/video and retained multiwindow guests
across launch, rotation, background return and recent-app switching.
Test pass alone does NOT establish universal third-party app compatibility.
