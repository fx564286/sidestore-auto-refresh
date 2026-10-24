# Scarlet Crystal V92 — cross-log audit, 2026-10-24

## Evidence boundaries
User-supplied report records and startup logs, not direct access to the iPhone's complete logs. App-reported installed version: 3.8.9 (3.8.192). The V89 unsigned IPA build alone does not prove that V89 code is installed.

## Repeated refresh issue
- Scheduled refresh 19:06:58–19:07:02: developer team verified, existing App ID found, App Groups assigned; then fetchProvisioningProfiles fails with code 3.
- Manual refresh 20:26:16–20:26:19: VPN peer 10.7.0.1:49152 reachable, RemotePairing tunnel succeeded, UDID fetched, team verified, cross-signed certificate valid, existing App ID found, App Groups assigned. Then fetchProvisioningProfiles exits with code 3.
- Manual run C4DE440C-66DA-4E97-AECC-962988B96132: stage=command; safe_cause=unknown; source_step=unknown.
- Manual run 13AF1A35-DC39-4301-B2F3-DF5930CC3E5C: same generic user-facing failure envelope. Its native substep log was not supplied.
- Target com.kdt.livecontainer is the logical refresh target; com.kdt.livecontainer.P8EZT3U5N4 is the expected team-signed ID. Their difference does not by itself prove incorrect signing. Do not reset App IDs without validated code-signature mapping.

## Independent issues also reviewed
- Explicit Keychain access group reports OSStatus -34018 even while local LC_KEYCHAIN items return 0. Requires a separate signed-entitlements and host/extension access-group investigation; not proof of general Apple account logout.
- SideJITServer not discovered; JIT unverified. Memory entitlement and extendedVirtualAddressing are not granted under the current observed free team.
- V75/V86 retained guest window registration can block reopening; actual device repair remains unverified.
- V72–V91 circular button/side Dock switching has had multiple iterations. V91 original Dock reuse is still a separate unfinished branch, not evidence of live feature success.
- Direct/Classic circular return path could restart Scarlet Crystal; V90 added explicit confirmation. LiveProcess path requests host scene activation.

## Root-cause conclusion and V92 change
The actual developer portal cause of profile operation code 3 is not identifiable from the available redacted error. The canonical lcProvisioningBundleRequest helper previously preserved typed signing context only for ServerError or pre-structured NSError, allowing other non-cancellation errors to lose signing source identity. V92 preserves structured signing/provisioning attribution and the native underlying error chain for all non-cancellation errors. Phase-enter and phase-pass markers distinguish app-ID registration, capability updates, App Group assignment, and profile-download entry. No Apple mutation, signing policy, certificate, App ID, app data, profile deletion, or guest UI behavior changes are made by this V92 patch.

## Acceptance test
On a signed iPhone build, retry once with logs enabled, and record the last SCARLET_V92_PROVISION phase-enter event plus its corresponding phase-pass, the error category and run correlation ID. Confirm profile retrieval success, then re-sign, device installation and verified terminal manifest before declaring the refresh repaired. Run a separate entitlement check for the Keychain explicit-group -34018 finding.
