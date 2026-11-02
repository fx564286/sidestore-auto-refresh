# V174 — independent root-cause review and release gate

Scope: Scarlet Crystal single LiveProcess IPA, iOS 27.2; no signing,
certificate, pairing-record, guest-container or iPad/windowed-guest changes.

## Three user-reported failures, accepted as reproduced
1. Portrait: controls behind upper system exclusion / not touchable.
2. Landscape: virtual app clipped or portrait-sized after rotation.
3. Instagram and other media: video does not advance.

## Reviewed source paths and observed conflicts
- V55 and V151 own native \`settings.frame\` and the maximized on-screen
  view frame; V139's media callback may request the host orientation.
- V169, V170, V171, V172 and V173 sequentially added multiple independent
  scene writers, cache invalidation and forced orientation. V173 retires the
  V170/171/172 writers but can still continuously invalidate V55 on a
  retained stale media surface.
- **Critical missing dimension**: pinned AppSceneViewController's modern
  iOS 27 \`updateSettingsWithBlock\` transforms \`tempSettings.frame\`
  and assigns \`contentView.frame\` separately from the actual attached
  scene controller bounds. Changing the decorated scene alone does not
  guarantee the rendered video surface follows it.
- On iOS 27 the upstream keyboard focus/event deferring support is already
  present. Avoid introducing a second media-specific audio/session hook.
- Logs for V173 3.8.247 prove RemotePairing UDID failure but do not contain
  a guest rotation/media render trace. Treat network refresh as a separate
  incomplete workflow, not proof of geometry or media success.

## V174 changes
1. Limit repeated V55 cache invalidation to one attempt per settled
   physical viewport generation, re-arm when geometry changes or stale
   surface clears. This avoids an unbounded layout feedback loop.
2. On iOS 27 only, the maximized attached rendered contentView uses
   the actual on-screen AppSceneVC bounds as its geometry, after UIKit
   commits matching window orientation and dimensions. Never resize
   the parent view, never overwrite portrait system exclusion, never
   affect windowed guest/PiP rendering or force an app's orientation.
3. Preserve guest FBS foreground lifecycle (V28/V104), upstream event
   deferring behavior and existing PiP audio owner. Do not claim the
   media decoder itself is fixed by a surface-alignment change.

## Automated release gates
- Focused V174 source regression tests and idempotent patch application.
- Repository fixture tests, strict preflight and pinned Xcode compilation.
- One unsigned IPA with version 3.8.248 / V174 identity and one artifact.
- No source patch writes keychain/UDID/VPN/provisioning/guest data.

## Device acceptance still required before marking fixes as resolved
- Portrait upper control fully visible and tappable after landscape return.
- Landscape remote content fills the intended host viewport without exposed
  SwiftUI edges or displaced touches.
- Instagram media plays progressing frames and audio, not merely a
  non-crashing AVPlayer host; check under both orientations.

Build success is not equivalent to acceptance. In-app evidence is currently
unavailable to CI.
