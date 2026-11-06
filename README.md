# Scarlet Crystal — New project

This repository branch is a **fresh source tree** for Scarlet Crystal, not an incremental V-series repair branch. Legacy application source, V-series scripts, obsolete iOS build pipelines, archived delivery assets and older patch chains are absent.

## Only four retained implementations

1. Native **Liquid Glass** renderer and gestures from existing Scarlet host, injected unchanged when host integration is built.
2. The pinned **LiveContainer** guest runtime, fetched from upstream.
3. The pinned embedded **SideStore** services and pairing, fetched from upstream.
4. Its pinned **SideSign** authentication and signing library.

Existing identity `com.kdt.livecontainer.P8EZT3U5N4`, Team `P8EZT3U5N4`, three extension IDs, signed App Group grants, user data and guest apps remain migration requirements (not deleted).

## New code

- `rebuild/Sources/ScarletCleanCore/`: independent Swift 6 action/update/provisioning policies.
- `rebuild/Sources/ScarletIndependentUI/`: independent UI and four native-glass destination tabs, one circular glass app-switcher, no separate window-manager tab.
- `rebuild/Tests/`: executable source/visual/renewal tests.
- `rebuild/scripts/scarlet_upstream_candidate.py`: new clean tracker for LiveContainer + embedded SideStore and nested SideSign.
- `.github/workflows/scarlet-clean-core.yml`: one gated build/test workflow.
- Figma: https://www.figma.com/design/QESg6S7oJS47PmlPpEX5w5

## Status and safeguards

**This is not an installable IPA.** Standalone Swift and iOS SwiftUI typechecks are necessary but not proof of host integration. To release: wire real engine and glass adapters, compile an integrated iOS host, verify 4-bundle provisioning and entitlements, non-destructive device install, working login/2FA, guest data and rotation. Personal Team 7-day expiry remains; re-signing and actual on-device reinstall are required.

The prior production branch and signed artifacts are not deleted by this source-tree replacement, so the user's installed app and currently usable signing route are not broken before a validated replacement exists. Legacy source does not exist on **this new branch**.
