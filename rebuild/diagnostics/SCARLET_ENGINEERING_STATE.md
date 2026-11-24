# Scarlet Crystal — engineering state / R6P134
Date: 2026-11-24 (UTC)
Baseline: R6P133, source 865f2257dd210906f7512c1c305fcd456c0945df.

## Requirements and acceptance
- Cumulative single IPA, original signed host and extension IDs, selected account isolation, existing SideStore shortcuts and native app pipelines preserved.
- Native foreground Shortcut without Minis/siboot: discover, verify newer release, pin owner and digest, install same identity, verify exact build/source after relaunch. No new App IDs or signing settings.
- Original and resident guest modes: Liquid Glass switcher, home return, recent apps, no hardware cutout overlap; no repeated P84 masking methods. Preserve landscape and native guest behavior.
- Never confuse native callback, CI artifact or simulator status with real iPhone installation/visual proof.

## Evidence observed
- R133 run 45347414255 four jobs success; device archive and release verified independently. IPA SHA256 a4eb8c21186fbe19d009a2d089659878968c6d668d102f3a64ed4a3e70ae4aba (42536848 bytes). Four packaged App Intents including ScarletSelfUpdateIntent; action discoverable in extracted metadata, not proof of iOS registration.
- R133 iOS 27.2 report session ac6487aa: 203 events. Seq8-27 classic handoff recovered 19 prior-process entries, switcher mounted/opened/closed/returned, scan complete, near=0 and severe=0 at mount and exit. Resident PID3562 seq165-166 near=5, severe=0, first rounded y60 vs safeTop62. No stable matching guest ID across modes: no definitive causal attribution. Seq183 interactive renewal deferred; seq189-193 certificate stored and wrong-team host resign blocked. Apple portal create error 20 remains. No shortcut dispatch or install readback recorded.
- R133 simulator artifact 14899047276: real xcodebuild linker error, iOS-simulator linked ScarletPairingFFI.a built for iOS. CI step continue-on-error did not validate simulator runtime.

## R134 implementation and next gates
- Transfer expected SHA256 to native installer, bounded worker-owned regular-file snapshot and digest verification before signer prepare; verify unsigned source/extension topology before portal requests and pin the exact installed host identifier instead of global appendTeamID. Retain final signed identity fence.
- SDK-qualified pairing library linkage and separate pinned simulator Rust target. Keep device archive bytes unchanged; improve diagnostic error extraction.
- Re-run full source suite, pinned upstream patch transformation, YAML and shell checks, L212 proposal and actual commit coverage. Native CI must build and package exact R134, manifest and IPA hash must match. Simulator must explicitly report compile/install/launch/screenshot stages; if unavailable mark blocked.
- Device acceptance outstanding: Shortcut discoverability, same-Team R133->R134 update (old client path) and R134->next verified release (new snapshot path), failure/cancellation, no duplicate ID, post-relaunch receipt. Need matched guest comparison for resident Island: preserve original mode evidence; distinguish SDK override, scene attachment and guest-local layout writer, no speculative geometry edits. Apple error 20 not a reason to revoke certificates. Test same and different account switching, refresh profile readback, installed catalog/artwork, audio pause/resume, gestures and landscape. No direct signed iPhone connection from NAS.
