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

Five editable iPhone concepts: Home, Apps, Settings, Connection & Signing, and Window Manager. Screen layers, text, colors and spacing are editable; preserved native Liquid Glass is marked as a runtime injection boundary. Existing runtime has **not** been replaced by these design frames.

## Implemented code in isolated branch

- `rebuild/Sources/ScarletCleanCore/ScarletActionCoordinator.swift`: new Swift 6 actor, explicit local vs service vs authenticated-service action policies, service outage does not block local actions; unknown install/signing results never claim success.
- `rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift`: independent SwiftUI home/apps/settings/connection shell. A callback invokes the existing **Liquid Glass window manager presenter**; the effect itself is not re-created.
- `rebuild/Tests/ScarletCleanCoreContract.swift`: executable core behavioral tests.
- `rebuild/Tests/test_independent_ui_contract.py`: preservation boundaries, real local routes, disabled states and iOS-safe layout checks.
- `.github/workflows/scarlet-clean-core.yml`: Linux Swift 6 behavioral contract plus Xcode 27.2 iOS-Simulator SwiftUI typecheck.

## Release gates (not complete)

1. Wire shell into pinned upstream LiveContainer host with one adapter to actual SideStore and SideSign operations (no V3 patch-stack accretion).
2. Preserve unchanged old Liquid Glass effect and guest controls by source diff and iPhone screenshot/interaction comparison.
3. Every visible button routes to a real local setting or authenticated service action; failures visible and non-destructive. Verify portrait/landscape safe areas and outside-tap dismiss.
4. Real iPhone pairing, Apple login and 6-digit 2FA, signing/provisioning and app installation must pass. A free Apple account cannot rely on Ad Hoc Safari OTA.
5. Xcode integrated unsigned IPA, matching four-bundle provisioning, signed IPA, non-destructive upgrade and verified real build label. Keep old V189 installed until those pass.

**Present state:** independent Figma designs + SwiftUI source + standalone and iOS typecheck only. The rebuilt host is not yet an installable IPA and actual SideStore/2FA remains unverified.

## Safety

No uninstall, App Group deletion, forced certificate/profile revocation or clearing guest data. Original V191 and earlier branches remain available for reference, not as a constraint on non-glass UI design.
