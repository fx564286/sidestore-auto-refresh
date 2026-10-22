# Scarlet Crystal V72 — Top-right overflow long press

**Requested behavior:** Stop exposing any Dynamic Island or adjacent-notch app-switch UI. Reuse the already-existing ellipsis at the **top-right of a virtual guest window**. Normal tap retains the existing Minimize / Maximize / Restore / Close menu; hold for 0.55 seconds opens a recent LiveContainer guest selector.

## Implementation

- V72 patch is applied **after** the previous fullscreen, V60 guest-route, V192 crash guard, and V66 main-app intent source patches. It removes the generated host's `ActivityKit` import, Activity attributes and manager, V56 overlay manager and SwiftUI bar, and V192 Activity-refresh callback. It removes the host Info.plist `NSSupportsLiveActivities` key.
- The original `DecoratedAppSceneViewController` overflow UIButton now has a long-press recognizer. Single-tap actions are intentionally left unchanged. Hold presents `UIAlertController` with up to eight currently running/recent (48 hours) guests from `DataManager.shared.model.apps` **only**.
- Retained in-process guests are resumed through `bringMultitaskViewToFront(uuid:)`. Other previously run container guests go through the existing `scarletcrystal251://livecontainer-launch` route with explicit container identity; the installed-catalog membership is rechecked on selection. A successful URL handoff is not yet proof the selected app launched correctly; real device validation remains required.
- Build feature policy sets `native_dynamic_island=false`; package `LiveWidget` and `AltWidget` extensions are forbidden. Preserve `ShareExtension`, `LiveProcess` and host App Intents, JIT controls, signatures, files and all existing guest data. **Unsigned build requires 3 distinct installable bundle IDs** (host, LiveProcess, ShareExtension). Actual Apple portal registration is not performed by this patch.
- V70 portrait-only bottom safe-area fix and landscape geometry stay unchanged. This UI is offered **only where the existing top-right overflow UIButton exists** (decorated virtual-window guest). Classic / LiveProcess guest screens without that button do not gain a new OS-level overlay; this is intentional.
- Old Live Activities from an earlier *installed* build may briefly outlive an upgrade until iOS retires them. The new app neither requests nor updates such Activities.

## Verification gates

- Run `tests/test_v72_overflow_longpress.py`, `tests/test_v68_appid_minimizer.py` and previous widgetless and IPA bundling checks.
- CI runs the V72 patch twice and checks generated Swift/Objective-C source, no `ActivityKit`, no V56 overlay and no live-activity plist key. The final unsigned IPA must contain `LiveProcess.appex`, `ShareExtension.appex` and no WidgetKit extension.
- Physical iOS 27.2 test: hold overflow > 0.55s, pick X/Instagram/KakaoTalk, verify guest window actually comes forward, test tap original window controls, rotate portrait/landscape, verify keyboard/JIT and no screen-covering bar. Until this is done, do not claim the interaction verified on an iPhone.
