# Scarlet Crystal native SideStore login audit (2026-11-06)

## Confirmed source behavior
- Pinned SideStore: `ee3cc16a67f9fed766f79a0ed70938f0f8ad5a07`.
- Native source login: `SettingsViewController.signIn() → AuthManager.shared.signIn(presentingViewController:) → SignInOperation.execute()`.
- Native 2FA handling: `SignInFlowHandler.verificationCode(for:)`, retaining trusted device, SMS, phone, six-digit prompt, cancel, retry. No new credentials UI or anisette mutations.
- Original Scarlet action `serviceBeginSignIn` previously launched SideStore home only; now passes `sidestore://signin` via LC's existing `runApp(urlStr:)` route.
- Rolled back the failing direct cross-file invocation of fileprivate `signIn()`. The adapter now calls `scarletStartNativeAppleSignIn()` added in the **same original** `AltStore/Settings/SettingsViewController.swift` file; this delegates to the unmodified native `signIn()` implementation.
- Scarlet settings `Apple ID 로그인` directly triggers native SideStore sign-in. No additional intermediate account/signing page is required. The existing navigation UI and host/guest data are preserved.
- SideStore home action, virtual guest launch, existing profiles and app data remain unchanged.

## Status semantics
The presence of an embedded SideStore framework is not proof of Apple authentication. Host does not read guest credentials; stale `false` flags remain unverified. Do not claim `-80045` fixed, Apple account authenticated, paired, or signing ready until device logs prove it.

## Blockers to use on the actual iPhone
1. Signed provisioning for host bundle `com.kdt.livecontainer.P8EZT3U5N4` and all three unchanged extensions. Confirm App Group entitlement in the actual profiles; previous profile refresh failed this guard.
2. Install and open the signed IPA on the real iPhone.
3. Tap `설정 → 연결 및 서명 → Apple ID 로그인 시작`; verify original native SideStore credentials screen appears, six-digit 2FA entry appears if Apple requests it, sign-in completes and persists across relaunch.
4. Separate tests for pairing, certificate, app signing, refresh, full LiveContainer guest launch and native Liquid Glass.

## Evidence required before declaring usable
- Device log from native `[SettingsVC] signIn()` and `[SignInOperation]` without secrets; authentication success with team identification redacted.
- Profile/entitlement audit of the actually signed IPA.
- Real device installation and application launch, not a simulator or source-level test.
- Auth failure `-80045` may still occur server-side even if native UI and headers are wired correctly.
