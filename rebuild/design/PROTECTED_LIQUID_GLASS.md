# Protected native Liquid Glass — original Scarlet Crystal implementation source

**Verification status: source provenance identified, new host integration BLOCKED.**

The new independent SwiftUI uses two required host inputs:
`preservedGlassTabBar(Binding<Tab>)` and `preservedGlassSwitchControl`.
These **do not themselves render the original effect**. The actual native
implementation must come from an audited production Scarlet source version,
not from Figma's backdrop blur or a new `.ultraThinMaterial` approximation.

The former Scarlet patch history (available in Git history and the preserved
legacy branch, **not imported as an old patch stack**) contains these origin
points:

- `scripts/patch_v131_reference_liquid_glass.py`: Swift/UIKit panel with
  `UIGlassEffect(style: .clear)`, `isInteractive = true`, a single native
  `UIVisualEffectView` and `SCNativeGlassRimView` optical edge. Old implementation
  edits generated `MultitaskSupport/MultitaskDockView.swift`.
- `scripts/patch_v144_button_glass.py`: UIKit touch-lens handling on a single
  host/guest button. Deliberately keeps the UIButton hit-test frame stationary
  and transforms only the visual effect child. Original code includes
  accessibility Reduce Motion behavior.
- `scripts/patch_v158_unified_action_glass.py`: equal recent-app and window
  manager panel geometry, action buttons do not clip on long press.

These scripts are **evidence of prior implementation choices**, not evidence
that V189/V190 or the new app works on the current iPhone. They are not
copied back into the clean source tree. The original host needs to be
extracted as a cohesive native component, reviewed for current iOS APIs,
and supplied through the required SwiftUI host adapter.

## Must prove before release

1. Actual code is the original native `UIGlassEffect` render path with no
   extra blur or second glass layer, and a meaningful diff/fingerprint.
2. One circular switcher; native glass tab bar with four destinations.
3. Real touch/long press, outside-tap dismissal, and orientation handling
   on a paired iPhone. No click-through, overlaid ghost windows or clipping.
4. Light/dark live background optical comparison versus a known-good
   user's earlier reference and the new Figma layout.
5. User's installed bundle and containers unchanged until verified upgrade.

Current automated readiness: `rebuild/scripts/audit_readiness.py` intentionally
reports **BLOCKED** because `rebuild/HostApp` and native host renderers do not exist.

Original source links:
- https://github.com/fx564286/sidestore-auto-refresh/blob/rebuild/scarlet-clean-core-20261106/scripts/patch_v131_reference_liquid_glass.py
- https://github.com/fx564286/sidestore-auto-refresh/blob/rebuild/scarlet-clean-core-20261106/scripts/patch_v144_button_glass.py
- https://github.com/fx564286/sidestore-auto-refresh/blob/rebuild/scarlet-clean-core-20261106/scripts/patch_v158_unified_action_glass.py
