# Scarlet Crystal — user-authored UI is the baseline

**Do not ship stock LiveContainer / stock SideStore UI as a "Scarlet Crystal
update."** Scarlet Crystal is an improved fork of these projects. Update the
underlying functionality from both parents while forward-porting the user's
visual and interaction layer. The user's design is not a replaceable skin.

## Protected visual/interaction behavior

- User-authored Liquid Glass controls: true native optical press/morph,
  perceptible translucency on light backgrounds, consistent rounded shapes.
- Recent Apps and Window Manager must use the same outer frame, tab dimensions,
  spacing, and touch target size. No accidental horizontal/vertical scrolling.
- Window action controls must retain size and never crop on long press.
- Tapping outside an expanded glass panel dismisses it on first contact
  in host and guest windows, without losing valid gesture ownership.
- Use **one** owner for the guest app control/LiveProcess route; no duplicate
  controls, legacy Direct overlay, or second UI implementation.
- Rotation, maximized guest scenes, safe-area frames, notch/button touch
  regions and landscape video viewport must not regress.

## Upstream strategy

1. Start from the coherent latest LiveContainer/main and
   LiveContainer/SideStore/LiveContainerSupport source graph.
2. Replay or forward-port **the original Scarlet UI changes**, checking
   canonical source anchors. If an anchor changed, review that behavior and
   rebase the patch. Do not silently remove a feature or substitute stock UI.
3. The source-level UI contract in `config/scarlet-ui-preservation.json`
   must pass before an unsigned IPA may be uploaded as a Scarlet candidate.
   `scripts/verify_scarlet_design.py` fails closed on missing features.
4. Source markers only prove source membership, not actual visual parity.
   Compare screenshots/recordings of portrait+landscape, dock collapse,
   tab switch, long press and outside dismiss on an iPhone before declaring
   the user-authored design preserved.
5. Always preserve installed bundle identity, profiles, pairing records and
   app data; do not reinstall a test IPA over the user's working app before
   signing and compatibility checks.

## Current candidate status

- V179: two-parent source compilation and unsigned IPA packaging **passed**,
  but **all eight custom UI contract checks failed**. It is NOT a valid
  replacement for the author's Scarlet Crystal design.
- V180: explicit UI-contract gate and latest-source forward-port attempt.
  Until the complete custom UI chain passes and the device visual regression
  is verified, V180 remains a blocked engineering candidate.
