# NRG LiveContainer + SideStore v3 — Physical iPhone Validation

Date: 2026-10-16
Build: https://github.com/fx564286/sidestore-auto-refresh/actions/runs/38819638038

## Verified outcomes
- Combined LiveContainer + embedded SideStore IPA: GitHub Actions build and packaging completed successfully.
- Existing Apple development certificate: local IPA signing completed successfully.
- Physical iPhone installation: **SUCCESS (reported by device owner)**.
- JIT activation: **SUCCESS (reported by device owner)**.

## Authentication and certificate investigation
- Earlier Apple ID authentication errors included -80045 and Anisette 503; following configuration/authentication changes, sign-in advanced to the Apple developer portal.
- Provisioning displayed **development certificate limit reached**, and the Settings screen showed **No active team** / provisioning needs attention.
- The embedded SideStore-to-LiveContainer JIT-Less certificate import showed: "The active SideStore certificate could not be imported."
- Relevant code paths: `importCertificateFromSideStore()`, `certExportActive`, active signing identity and PKCS#12 validation.
- Existing certificate/private key reuse was investigated; do not revoke certificates automatically.
- LocalDevVPN / Remote Pairing investigation observed `deviceEndpointIp is nil` and UDID discovery failures.

## Build and delivery
- GitHub Actions run 38819638038 passed CoreDevice transport testing, iOS idevice compilation, host/embedded SideStore build, IPA packaging, and artifact verification.
- The IPA was signed locally using the existing developer identity, retaining the installed app's bundle identifier.
- A HTTPS OTA manifest and installation page were prepared; a separate .mobileconfig generated for this release is only a **WebClip shortcut**, not an app installation payload.
- Device owner subsequently confirmed successful installation and JIT activation. This confirms the user-observed outcome, not the internal cause or success of every auth/JIT-Less code path.

## Validation matrix
| Area | Status |
| --- | --- |
| Combined IPA CI build | PASS |
| IPA signing | PASS |
| iPhone installation | PASS — owner confirmed |
| JIT activation | PASS — owner confirmed |
| Apple ID sign-in end-to-end | Pending final confirmation |
| Developer team provisioning | Previously blocked by certificate limit; pending |
| JIT-Less SideStore active certificate import | Previously failed; pending |
| Remote Pairing / UDID | Previously failed; pending |

## Developer follow-ups
1. Preserve the successful JIT activation path and add regression coverage.
2. Confirm Apple ID authentication → developer team → existing certificate reuse → provisioning.
3. Add precise non-sensitive diagnostics to `certExportActive` and certificate import continuity checks.
4. Validate JIT-Less certificate import separately from JIT activation.
5. Validate pairing record UDID and LocalDevVPN device endpoint discovery on a physical device.
6. Never upload Apple account credentials, private keys, OTPs, pairing records or unredacted authentication logs.

Evidence: https://github.com/fx564286/sidestore-auto-refresh/actions/runs/38819638038
