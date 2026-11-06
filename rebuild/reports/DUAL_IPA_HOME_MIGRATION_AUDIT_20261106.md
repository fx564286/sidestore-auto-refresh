# Scarlet Home dual IPA install / engine-only audit — 2026-11-06

## Existing integrated installation references
- Existing Scarlet branch `fix/scarlet-v190-auth-transport-20261106`, host UI `scripts/templates/v3_unified_shell.swift`.
- Original host-installed iOS IPA path: `V3InstallButton` → `stagePickerIPA` → `V3IPAStaging` → SideStore service operation `installSharedIPA`, with private App Group token, preflight and mutation recovery.
- Guest IPA import remains a separate LiveContainer operation, with native `LCAppListView` file importer.
- Rebuilt Home has two distinct actions in ONE screen: `iOS 앱 설치` (`serviceInstallIPA`) and `게스트 앱 설치` (`localImportGuestIPA`).
- Device IPA installation in the rebuild is STILL FAIL-CLOSED because the original service transport and profile entitlement path are not yet safely ported. A button shown is not proof of install success.

## Wrong integration code removed
- The experimental anonymous XPC authentication branch was rolled back in research commit `c0e5470847b558b513decace0f532f3cc2583210`, preserving its historical audit.
- Redundant `SideStore 열기` navigation from Settings → Connection was removed; SideStore serves as an engine, not a guest UI destination.
- The original LiveContainer guest importer, original SwiftUI settings, native Liquid Glass, existing bundle ID `com.kdt.livecontainer.P8EZT3U5N4` and three extensions are preserved.

## Unverified release gates
Apple login and 2FA in Scarlet UI; App Group entitlement consistency; old valid certificates/profiles preservation; request-owned SideStore `installSharedIPA` service/receipt; signed IPA readback; real iPhone installation and runtime. Do not conflate source compilation with user-device success.
