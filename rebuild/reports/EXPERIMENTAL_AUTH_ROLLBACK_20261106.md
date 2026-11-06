# Experimental authentication rollback / 2026-11-06

## Scope and exact refs
- Research branch prior HEAD: `e5b14f8ca7f2c4866eb05e4c6a3295e5e00102d1`.
- Stable rebuilt branch: `01e13113d07b29bb3e235a5ba7b420a294444551` (Xcode host+SideStore build and SwiftUI tests previously passed).
- This commit restores the stable tree onto the research branch WITHOUT a force-push. Historical experimental commits remain visible for audit; no installed user app or provisioning record is touched.

## Confirmed incorrect changes
1. `patch_host_auth_ipc.py` changed original LC Xcode target dependencies and introduced a dynamic Objective-C invocation for credentials; initial CI failed at a nonunique target dependency anchor.
2. `patch_sidestore_headless_auth.py` modified SideStore's `SignInOperation` sign-out failure behavior without demonstrating equivalence to original certificate/credential lifecycle.
3. `ScarletSideStoreSupportAuth.swift` and `ScarletLiveContainerSignInEngine.swift` connected host secret entry to an unverified anonymous NSXPC and background guest lifecycle.
4. Prototype linked the experimental interface as if authentication were ready without real login, 2FA, registration, profile, signature or installation verification; subsequent research host Xcode build failed (run 42177528301). These changes are inappropriate on a production candidate.

## Rollback
Restore the stable tree, including original pinned SideStore and SideSign sources and first-party Scarlet sign-in form with disabled submit until a verified backend is connected. Do not patch SideStore password storage, certificates, provisioning, app groups, or guest app data.
- No `patch_host_auth_ipc.py`
- No `patch_sidestore_headless_auth.py`
- No experimental `ScarletLiveContainerSignInEngine.swift`
- No `ScarletSideStoreSupportAuth.swift`
- No unsafe dynamic runtime credential invocation

## Acceptance
The stable branch is not automatically a signed or fully usable app: SideStore engine-only Apple login and iPhone signing/install remain unverified. Restored code does not imply Apple sign-in success.
