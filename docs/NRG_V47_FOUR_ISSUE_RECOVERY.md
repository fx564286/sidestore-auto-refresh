# NRG V47 — Four-issue recovery, validation and limits

This is a **candidate patch**, not a declaration that four device problems
are solved. No certificates, provisioning identities, guest app data or
registered Apple App IDs are revoked or deleted.

| Issue | Evidence / risk | V47 change | What remains unproven |
| --- | --- | --- | --- |
| 1 — Apple App ID registration | `appIDLimitReached`; prior local count showed `registered=7, available=3` but the server rejected the request | Fetch fresh Apple App ID inventory before free-team install and label the local budget as an **estimate**. Keep the V46 no-delete, exact-ID four-profile upgrade path. | Apple server's weekly/team limit cannot be bypassed, and any absent exact profile still blocks installation. |
| 2 — JIT | SideJIT service discovery may fail; Madeira reported `attached` but optional remote-debug packets `QSetIgnoredExceptions -> E35` / `QPassSignals unsupported` | If an external SideJIT server returns 502/503/504, fall back to the existing paired-device debugger. V46 already handles absent servers and transient network errors. No false runtime-JIT success claim. | Madeira/LLDB target JIT code execution, iOS debugger permissions, and live device integration. `attached` alone is insufficient proof. |
| 3 — Keyboard and audio after long app switch/offline | Initial success, failure after a different app or prolonged background | On host scene activation, re-foreground only an already running, visible, non-PiP guest in the same `UIWindowScene`. Do not globally dismiss keyboard or force a process-wide audio session. | On-device keyboard typing and actual sound after 30 s, 5 min, 20 min, offline, lock/unlock, app switching, and PiP transitions. Audio may require a separate guest-process interruption handler if scene restoration alone is insufficient. |
| 4 — Memory limit | Apple capability requested by V33, but actual granted entitlement must come from profile | Log per-profile `com.apple.developer.kernel.increased-memory-limit` entitlement grant during existing-profile installation. | A true profile grant does not imply unlimited RAM. iOS jetsam/process limits remain OS-enforced; a free team may be denied the entitlement. |

## Additional evidence: Keychain

`keychainExplicitGroupUnauthorized` (`OSStatus -34018`) was reported while
ordinary process-scope storage remained accessible. This should be independently
verified with the actual signed IPA's entitlements and `embedded.mobileprovision`
before changing app/keychain group IDs. Changing IDs or deleting credentials
without that evidence can destroy the reuse path.

## Safe device acceptance

1. Back up the existing installed NRG and its data; preserve the original host
   Bundle ID and three extension IDs.
2. Run the existing widgetless four-profile upgrade path. If a required profile
   is missing or Apple denies its creation, **stop**; do not uninstall NRG.
3. For JIT, check a real guest's JIT-required workload instead of only LLDB
   attachment or the launcher's return URL.
4. For keyboard/audio, type and play audio after each background/offline
   scenario; record guest PID, foreground events and audio interruption state
   without exporting passwords or private data.
5. For memory, record the signed provisioning profile's entitlement and test
   actual per-process memory under normal iOS constraints. Never advertise an
   ungranted capability or an unsupported OS-level memory bypass.

## Verified locally

- V47 Python unit tests.
- Existing pinned LiveContainer transform chain V27 → V28 → V46 → V47
  (source-level only).
- Existing pinned SideStore JIT transform chain V43 → V45 → V46 → V47
  (source-level only).
- Bash syntax audit of the existing no-delete upgrade script.
- Device signing / Xcode build / runtime **not** verified in the local Linux
  environment. GitHub Actions compilation and device acceptance are distinct.
