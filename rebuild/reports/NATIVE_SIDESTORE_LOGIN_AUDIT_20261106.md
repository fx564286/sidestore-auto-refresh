# Scarlet-only Apple sign-in architecture (2026-11-06)

## User-required behavior
- Scarlet Crystal renders Apple ID, password, and one-time code inside its OWN interface.
- SideStore guest AuthenticationViewController, SideStore settings login page, and `sidestore://signin` redirection are forbidden.
- Reuse original SideStore/SideSign authentication, 2FA, Anisette, team/certificate/profile persistence using a safe transport. Do not reimplement portal behavior.

## Applied source changes
- Reverted the injected guest SideStore login URL router and cross-file native Settings signIn entry; SideStore source is now unpatched/pinned again.
- Scarlet settings action `serviceBeginSignIn` presents the standalone `ScarletAppleIDLoginSheet`; original native SideStore app launch is retained only for deliberate SideStore app navigation.
- Added `ScarletAppleSignInEngine` contract for an async engine operation, with a six-digit code callback and an explicit unconnected bridge.
- The form holds password/code ephemerally and clears them on submit/dismissal. Secrets never go into launch URL, UserDefaults, application-group files, or diagnostic logs.
- Login submission is **disabled** until the SideStore engine is actually bound. This is NOT a verified usable login.

## Remaining engineering blockers
1. The SideStore executable is packaged as a LiveContainer guest and does not expose a callable host-side authentication service.
2. A secure runtime transport (or extraction/linkage of the original SideSign auth service) must be implemented with original credential, 2FA, certificate and team workflows. No password-through-URL, no storage of raw secrets in an App Group.
3. End-to-end signed device test must verify real Apple login, 2FA, team/certificate/profile persistence, app installation and the historical `-80045` case.
4. Existing App Group entitlement mismatch in newly refreshed profiles must be fixed without stripping entitlements or deleting old certificates.

## Status
- UI routing and source-level fail-closed safety: pending CI verification.
- Engine-only authentication in Scarlet host: **NOT CONNECTED**.
- Signed IPA and real device authentication: **UNVERIFIED**.
