# V95: October 24–25 Scarlet Crystal device-log audit

Evidence scope: user-supplied logs and Setup Assistant summary, not direct device-file access.

## Confirmed refresh failure sequence
- Oct 24 19:06 scheduled: Team, App ID, App Group passed; failed in FetchProvisioningProfiles (redacted code 3).
- Oct 24 20:26 manual: VPN 10.7.0.1, RP pairing, UDID, certificate verified; failed in FetchProvisioningProfiles (redacted code 3).
- Oct 24 22:06 multiple sequential requests: V92 phase markers show main profile_download entered after App Group success and failed; no installed profile proof.
- Oct 25 03:13:51 scheduled, 03:13:59 manual, 03:14:07 manual: V93 typed log shows portal_server_reported_wrapped and portal_code=8220 at main profile retrieval. These are sequential, not simultaneous.
- No profile-retry success, signing/installation completion or run-scoped verified terminal manifest appears in the supplied logs.

## Source root cause
- DeveloperPortalProxy calls lcPortalSigningRequest, which wraps typed ServerError 8220 as an NSError containing LCStructuredSigningContextV1 and LCStructuredFailureSourceV1.
- V77 previously catches only a direct ServerError. Because the original was wrapped, V77 could not enter its device-registration check and single retry. There are no LC_V77_PORTAL_DEVICE messages in these logs.
- V95 recognizes only typed 8220 or a provenance-checked wrapped error: typed_error=sideSignServerReportedError, server_code=8220 and source=provisioningProfileRetrieval.
- Existing bounded recovery then queries registered devices for the same team, uses the currently paired trusted UDID and registers it only if missing, then retries one profile download. It cannot guarantee Apple accepts the retry.

## Misleading last verified date
- Setup Assistant displayed Last verified refresh at 03:14 despite three visible failures.
- refreshVerificationRow previously copied manifest.date even for failed attempts. V95 reads only liveContainerAutoRefreshLastSuccessfulRefresh, written in markVerified after complete verification.
- This establishes a UI evidence bug, not proof that no separate success ever occurred outside the supplied excerpt.

## Separate outstanding issues
- Keychain explicit-group permission failure OSStatus -34018 coexists with per-process keychain status 0.
- SideJITServer not discovered; extended VA not granted; increased memory/debugging entitlements dropped by free team.
- CoreDevice is not checked/verified by Setup Assistant; RemotePairing successful UDID fetch is not proof of CoreDevice install transport.
- Logical refresh ID com.kdt.livecontainer vs desired signed identity com.kdt.livecontainer.P8EZT3U5N4 requires signed provisioning inspection before any rewrite or deletion.
- Guest-process orphan windows, Direct-mode return motion and the V91 original Dock long-hold feature need independent signed-device validation.

## Acceptance
- Gate V95 on macOS Xcode 27.2 compiled/generated Swift and regression tests.
- On a signed iPhone build, require LC_V77_PORTAL_DEVICE recovery progress and a valid installed manifest before claiming refresh success.
- No profiles, Apple App IDs, certificates, team identities or installed guest data should be deleted as a diagnostic shortcut.