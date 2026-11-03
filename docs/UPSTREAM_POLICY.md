# Scarlet Crystal upstream compatibility policy (V177)

Scarlet Crystal is an independently modified **derivative of two software
projects**, not a permanent fork frozen at historical source revisions:

1. **LiveContainer/LiveContainer** `main`: container host, guest process,
   multitasking, rotation, window controls, native glass and extensions.
2. **LiveContainer/SideStore** `LiveContainerSupport`: embedded installation,
   automatic refresh, pairing, developer-portal integration and signing.

**SideStore/SideStore** `develop` is tracked as an independent upstream
advisory feed. Its head must not be substituted for `LiveContainerSupport`
without a deliberate integration review.

## Coherent source graph

`LIVE_CONTAINER_REF` is the exact upstream LiveContainer commit.
`EMBEDDED_SIDESTORE_REF` is the exact `LiveContainerSupport` commit.
`MINIMUXER_REF` and `SIDESIGN_REF` MUST equal the gitlink SHAs in the
chosen embedded SideStore commit. A standalone idevice commit must remain
ABI-compatible with the selected minimuxer Swift gateway and local Rust
patches: never downgrade solely to conceal a compiler failure.

`scripts/scarlet_upstream_follow.py` resolves the pair and validates that
graph before staging changes. It never updates signing or user state.

## Overlay maintenance, not patch accumulation

Carry Scarlet-specific code as explicit, reviewed overlays on top of fresh
upstream sources. If an overlay conflicts with upstream, identify its
behavioral invariant, compare the upstream implementation, then port only
necessary changes. Retire patches when upstream implements the same feature.
Do not forward-port a patch by grepping stale source blindly.

## Promotion gates

- Confirm upstream SHAs and nested gitlinks; record a provenance manifest.
- Pass Swift/Rust compilation and direct API/ABI conformance tests.
- Pass pairing, signing, refresh, CoreDevice and all retained app tests.
- Verify a real unsigned IPA including expected host and extensions.
- On iOS hardware, test RP handshake, UDID, installation, refresh, guest
  process, Liquid Glass, outside-tap, screen rotation and app data continuity.
- Preserve bundle identity, provisioning, certificates, pairing records,
  user data and app assets. Never auto-delete or auto-repair with new credentials.

Upstream tracking may stage an update PR, but may NOT auto-merge, release,
sign or install a candidate. **CI green is not a device functional pass.**

As of 2026-11-03, the V177 branch is a candidate *source baseline*; the
historic Scarlet overlay must still be revalidated on both latest trees.
