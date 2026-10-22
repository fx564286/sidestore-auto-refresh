# Scarlet Crystal V67: exactly three App IDs, expandable APIs

## Hard deployment boundary

Keep **the same installed host ID** `com.kdt.livecontainer.P8EZT3U5N4` and its
previously registered `LiveProcess` and `LiveWidget` suffix IDs. Packaging must
never introduce a fourth app/extension ID. The three ID names inside an unsigned
IPA have the `com.kdt.livecontainer` prefix before signing; the signer's final
profiles must map all three to the already registered free-team IDs.

- Host: SideStore backend, Apple API adapters, app shortcuts, UI, document import,
  JIT orchestration and custom user API clients.
- LiveProcess: iOS extension process used for existing guest execution.
- LiveWidget: native WidgetKit / ActivityKit dynamic-island UI.
- No `ShareExtension`, no `LaunchAppExtension`; the original upstream extension
  sources remain available for future compatibility review, not installed.

## Intentional capability boundary

The original host Info.plist already registers the `public.item` document type,
`LSSupportsOpeningDocumentsInPlace` and custom app URLs. Existing file import
and copied launch URL paths must be validated on device. **Native share-sheet
receiver** and its guest chooser require an additional share extension and
cannot be kept under the strict 3-ID cap. This is a known trade-off, not a
claim of feature parity. Equivalent source-app interactions may be rebuilt via
Share > Open In or Files, when the source app offers them.

## API expansion rules

Native system frameworks, custom Swift Packages, C/ObjC APIs and network APIs
belong to the existing app bundle or a framework, not a new `.appex`. Widget
features live inside the existing LiveWidget. The API registry in
`config/v67_api_modules.json` describes feasible placement and restrictions;
it does **not** grant Apple entitlements. Prevent any SDK upgrade from adding
new `.appex` payloads or hard-coded provisioning identifiers by checking the
archive and all nested bundle identifiers.

## Latest compatible rather than newest untested

- Check LiveContainer main and the combined SideStore upstream daily.
- Record upstream Git SHAs and observed Xcode/iPhoneOS SDK revision.
- Alert in GitHub Issues when source pins lag upstream; check downstream APIs.
- Compile in a new candidate pipeline using a newer SDK/pinned commit, run
  source and device regression tests, then promote only on confirmed compatibility.
- Keep stable pins until the candidate passes; do not silently auto-upgrade
  signing or App ID entitlements, and do not put Apple private signing keys on CI.

A workflow with `schedule` **only executes when this file is on the GitHub
repository's default branch**. The isolated V67 build branch itself does not
activate daily checks without the separate default-branch watcher.
