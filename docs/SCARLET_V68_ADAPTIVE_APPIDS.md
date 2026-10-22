# Scarlet Crystal V68 — minimum necessary App IDs, not a fixed 3

**Objective:** minimize *registered native app/extension identifiers*, while
preserving every required user-facing capability. An API or module can use the
existing host when iOS allows it. A native extension that requires its own
extension point cannot simply run as an unregistered LiveContainer guest.

`config/v68_required_features.json` is the source of truth. The build's
`v68_appid_minimizer.py` chooses the required installable components and writes
`artifacts/minimum-appids.json`, then verifies that the actual IPA contains
exactly those components. Unknown future Apple APIs fail closed until mapped to
an app-hosted framework, an existing extension, or a new required extension.

| Native feature requirements | Plan | Count | Current implementation |
|---|---|---:|---|
| Guest management only | Host | 1 | architectural exploration, unimplemented |
| Guest management + native Dynamic Island | Host + LiveWidget | 2 | missing separate guest capability, unimplemented |
| + independent guest execution, with Shortcuts as sharing substitute | Host + LiveProcess + LiveWidget | 3 | V67 packaging candidate, native share-sheet target lost |
| + actual native iOS share-sheet receiver | Host + LiveProcess + LiveWidget + ShareExtension | **4** | V68 build candidate; preserves native share receiving |

`LaunchAppExtension` is not included because `App Intents` has been moved to
host code in V66; this migration itself still requires macOS build and device
verification. No new Apple App ID is needed for Swift Packages, common native
frameworks or the user's API clients merely because their number increases.
Entitlements, provisioning and SDK requirements are separate gates.

This is **feature-based minimization**, not a proof that 4 is the absolute
minimum possible under an entirely new iOS architecture. Do not silently remove
`LiveProcess` (used for separate guest process/multitask) or `LiveWidget`
(required for native WidgetKit / Live Activities). Alternative architectures may
reduce the count but must be implemented and tested before being called working.

The previous V67 profile that removed ShareExtension is still selectable by
changing `native_share_sheet_receiver` to `false`, with the explicit difference
that a Shortcuts share action is not a native share extension destination.
Do not delete existing Apple portal App IDs solely because a new unsigned IPA
no longer contains an extension; verify the installed app, refresh status and
availability on the actual free-team account first. The original V65 branch is
preserved. Upstream and Apple SDK tracking remains independent of ID selection.
