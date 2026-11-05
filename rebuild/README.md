# Scarlet Crystal — clean-core rebuild (isolated baseline)

**Not an installable IPA, not a successful SideStore repair.** This folder
implements the first verified boundary of the replacement application
architecture, without changing the user's installed app, certificate or data.

## Existing assets that MUST remain identical

| Asset | Canonical value/policy |
| --- | --- |
| Product | Scarlet Crystal |
| iOS host bundle ID | `com.kdt.livecontainer.P8EZT3U5N4` |
| Apple free team | `P8EZT3U5N4` |
| Extensions | LiveProcess, ShareExtension, LaunchAppExtension |
| App Group | retain existing authorized group and access to existing data |
| External parents | pinned LiveContainer and embedded SideStore, not a copy invented here |
| Liquid Glass / gestures / windows | preserve original custom user-authored implementation, no notch feature |
| Stored app data / accounts | no forced uninstall, reset, profile deletion or revocation |
| Signing | development-sign existing bundle set; free account does not confer Ad Hoc OTA |

## Reason for rebuild

The V189 physical iPhone log shows `auth.rpc.lease_waiting` without a
subsequent connect or send event. V191 bounds that waiting path but does not
prove a working service. The settings UI separately gates SideStore-backed
toggles on a stale snapshot, which makes many controls appear inert.
Repeatedly forward-porting V3 patches is hard to validate as an app.

## Replacement, in order

1. **Working standalone interaction coordinator:** local action and service
   action use distinct adapters and typed receipts. A broken service cannot
   block native settings; an unverified remote write never claims success.
2. Replace the host settings view using one unified action inventory and
   trace every button's tap, disabled reason, request, result and persistence.
   Distinguish UserDefaults, files, service settings and Apple authorization.
3. Replace the V3 auth bridge with one session owner, one authoritative
   SideStore connection, explicit reconnect/reset rules and a time-bounded
   pre-XPC request lifecycle; no invented Apple 2FA results.
4. Integrate upstream LiveContainer + SideStore source and preserve the old
   Liquid Glass dock/guest control flows as data and tested design invariants.
5. Execute iOS builds plus navigation/rotation/control tests and prove
   compatible signing of all 4 bundles before delivering IPA. Install without
   deleting the existing application. Re-verify password/2FA separately.

## Verification evidence and limits

- `rebuild/Sources/ScarletCleanCore/ScarletActionCoordinator.swift` is new,
  independent source: no legacy V3 import or old-state patch stack.
- `rebuild/Tests/ScarletCleanCoreContract.swift` runs executable tests for
  disconnected native settings, service-backed actions, authentication
  gates, and no false installation success.
- CI: `.github/workflows/scarlet-clean-core.yml`.
- **Passing standalone tests do not mean the app is rebuilt.**
  Real iOS integration, UI parity, Apple login, signed IPA and the user's
  installed runtime remain separate unverified gates.

## Safeguards

The original V191 and older release branches are preserved for comparison;
this rebuild must not silently merge or overwrite them. No destructive
migration is permitted. Keep a read-only compatibility test for existing
guest containers, profiles and App Group access before any on-device upgrade.
