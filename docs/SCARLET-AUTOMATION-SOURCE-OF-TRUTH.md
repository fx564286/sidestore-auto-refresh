# Scarlet Crystal: durable automation source of truth

**Reason for automation:** The owner should not need to re-explain the same instructions in future ChatGPT conversations or manually repeat per-version signing, uploading, and installer link creation. This is NOT primarily a new feature request or a complaint that every app feature fails.

## Unchanging requirements
- Project: Scarlet Crystal, a customized LiveContainer + SideStore fork; preserve original Liquid Glass, app containers and user data.
- Apple Team: `P8EZT3U5N4`; host bundle `com.kdt.livecontainer.P8EZT3U5N4`; extensions `.LiveProcess`, `.ShareExtension`, `.LaunchAppExtension`.
- Preserve original App Group `group.com.SideStore.SideStore.P8EZT3U5N4`.
- GitHub project: `fx564286/sidestore-auto-refresh`; installation entry point stays `https://fx564286.github.io/sidestore-auto-refresh/scarlet-latest.html`.
- iPhone uses built-in Safari on **Wi-Fi, LTE and 5G**, no SSH/Termius application or LAN connection. Do NOT ask to change mobile network settings for app installation.
- Only the CachyOS PC holds the Apple private signing key and profiles. Never push private key, P12, password, SSH key or bearer tokens to GitHub or iOS Shortcut.
- Do not revoke Apple certificates, alter provisioning App IDs, delete the installed app or replace Liquid Glass without explicit authorization.
- NEVER mistake: GitHub CI build vs signed IPA vs upload vs on-device installation vs successful login/2FA.

## Reproducible chain (same steps for every future release)
1. GitHub Actions macOS Xcode integration produces an artifact named `Scarlet-Crystal-V{N}-...-UNSIGNED`, with a verified SHA256 JSON receipt.
2. On the PC, local scheduled publisher discovers successful owner Xcode runs, checks SHA256 and actual CFBundleVersion and ScarletBuildLabel, and selects the highest verified version. A stale `#191` UI display is NOT authoritative.
3. Local Apple authorized PEM key and four App Group-enabled profiles sign the IPA; preserve original host and three extension IDs; verify all Mach-O signatures and embedded profiles.
4. Upload signed IPA to `scarlet-v{N}-device-signed-YYYYMMDD`, publish `Scarlet-V{N}-SIGNED-manifest.plist`, checksum, and version-specific `scarlet-v{N}.html`.
5. The fixed `scarlet-latest.html` installation page dynamically selects the highest signed release and checks release asset SHA256 against the public checksum and manifest before exposing the installation button.
6. An iPhone attempts to install; actual device installation, data, authentication, 2FA and Liquid Glass state are independent observations.
7. No duplicate re-signing/updating when a valid identical signed release is already published. On errors, preserve the last verified signed build and record the first blocking error.

## Current verified vs NOT verified (2026-11-05)
- V188 new Apple certificate and four development profiles validated; original App Group preserved; V188 actual signed IPA published.
- V189 separate signed **development** IPA published to GitHub (not the same as actual device install).
- The fixed `scarlet-latest.html` page is published to GitHub Pages.
- An earlier **NAS SSH** iPhone shortcut was signed but failed to connect from external cellular; it is NOT the recommended future primary path.
- The installed iPhone build and successful iOS OTA installation are **not verified**.
- **Apple Development-signed IPA may be refused by Safari OTA.** Generating a manifest does not make a development profile an Ad Hoc/Distribution profile.
- Automatic publisher script exists but a persistent PC systemd timer has **not yet been installed and verified**.

## Operator policy for future assistants
Read this document and actual GitHub CI/release/status before suggesting changes. Continue the same workflow, do not start a new competing installer, force manual SSH on the phone, invent a claimed V{N} install, conflate login vs 2FA vs pairing, or repeat previously ineffective steps. State actual verified status with evidence.
