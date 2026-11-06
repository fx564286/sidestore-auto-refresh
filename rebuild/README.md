# Scarlet Crystal — independent UI rebuild

**Scope fixed 2026-11-06:** only the existing **native Liquid Glass effect**, **LiveContainer guest engine**, **SideStore services**, and **SideSign library** remain as protected runtime implementations. All other presentation, controls, settings, navigation, diagnostics, status screens and information architecture may be redesigned independently. Host identity and user data must still remain compatible.

## Protected runtime and identity

| Area | Required boundary |
| --- | --- |
| Native Liquid Glass | Keep existing effect code, gesture behavior and host presenter. New UI calls into it; do **not** fake/reimplement the material. |
| LiveContainer | Keep guest execution/runtime engine and the single LiveProcess control route. |
| SideStore | Keep the actual embedded service and pairing/auth/install behavior behind a clearly typed adapter. |
| SideSign | Keep authentication and Apple-signing library; do not replace or invent Apple credentials. |
| Identity | Scarlet Crystal `com.kdt.livecontainer.P8EZT3U5N4`; team `P8EZT3U5N4` and existing extensions. |
| App Groups / user data | Preserve exact existing authorized groups, certificates, installed guests and host documents. No destructive reset. |

**The legacy `config/scarlet-ui-preservation.json` is historical for V144–V191 builds; it does not restrict the new independent UI.** Only the glass *effect and interaction implementation*, not the old non-glass layout, sizes, colors, positions or menus, is frozen. No notch or Dynamic Island integration.

Authoritative boundary: [`rebuild/config/scarlet-independent-ui-contract.json`](config/scarlet-independent-ui-contract.json).

## Editable design

[Figma — Scarlet Crystal · Independent UI Rebuild](https://www.figma.com/design/QESg6S7oJS47PmlPpEX5w5)

The **original four bottom destinations** (Home, Apps, Sources, Settings), a Settings → Account & Signing detail view, and one **overlay preview** for recent apps / window management. These are six editable Figma frames (four destination screens, one detail view, one overlay). The overlay is opened only by the existing round app-switcher, **not** a fifth page or tab. Figma glass is a visual preview; the shipped iOS bar and switcher must reuse the host's original native Liquid Glass effect and gestures. Existing runtime has **not** been replaced by these design frames.

## Implemented code in isolated branch

- `rebuild/Sources/ScarletCleanCore/ScarletActionCoordinator.swift`: new Swift 6 actor, explicit local vs service vs authenticated-service action policies, service outage does not block local actions; unknown install/signing results never claim success.
- `rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift`: independent SwiftUI Home/Apps/Sources/Settings shell with Settings → Account & Signing detail with **both host-injected original Liquid Glass controls**: `preservedGlassTabBar(Binding<Tab>)` for the persistent four-destination bottom dock and `preservedGlassSwitchControl` for app switching and window management. The effect itself is not re-created.
- `rebuild/Tests/ScarletCleanCoreContract.swift`: executable core behavioral tests.
- `rebuild/Tests/test_independent_ui_contract.py`: preservation boundaries, real local routes, disabled states and iOS-safe layout checks.
- `.github/workflows/scarlet-clean-core.yml`: Linux Swift 6 behavioral contract plus Xcode 27.2 iOS-Simulator SwiftUI typecheck.

## Release gates (not complete)

1. Wire shell into pinned upstream LiveContainer host with one adapter to actual SideStore and SideSign operations (no V3 patch-stack accretion).
2. Preserve the original native Liquid Glass bottom bar and circular switcher including long-press/gesture behavior, with exact host adapter injections and iPhone screenshot/interaction comparisons. Confirm the exact original destination tabs are Home, Apps, Sources and Settings; Account & Signing lives inside Settings; the window manager remains an overlay.
3. Every visible button routes to a real local setting or authenticated service action; failures visible and non-destructive. Verify portrait/landscape safe areas and outside-tap dismiss.
4. Real iPhone pairing, Apple login and 6-digit 2FA, signing/provisioning and app installation must pass. A free Apple account cannot rely on Ad Hoc Safari OTA.
5. Xcode integrated unsigned IPA, matching four-bundle provisioning, signed IPA, non-destructive upgrade and verified real build label. Keep old V189 installed until those pass.

**Present state:** independent Figma designs + SwiftUI source + standalone and iOS typecheck only. The rebuilt host is not yet an installable IPA and actual SideStore/2FA remains unverified.

## Safety

No uninstall, App Group deletion, forced certificate/profile revocation or clearing guest data. Original V191 and earlier branches remain available for reference, not as a constraint on non-glass UI design.
