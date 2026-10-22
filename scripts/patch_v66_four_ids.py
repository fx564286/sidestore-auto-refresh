"""Move the Launch App shortcut from an extension into the containing app.

Opt-in only: this patch is used on the experimental 4-App-ID branch.
The stock LiveContainer checkout and the V65 baseline remain untouched.
"""
from pathlib import Path
import sys

SWIFT = r'''// NRG_V66_FOUR_IDS: app-hosted replacement for LaunchAppExtension.
import Foundation
import AppIntents
import UIKit

@available(iOS 16.0, *)
struct ScarletCrystalLaunchAppIntent: AppIntent {
    static var title: LocalizedStringResource { "Launch App" }
    static var description = IntentDescription(
        "Open a LiveContainer guest using its copied Launch URL."
    )
    // This intent resides in the MAIN app; background extension invocation
    // is intentionally replaced by foreground delivery to the app's URL router.
    static var openAppWhenRun: Bool { true }

    @Parameter(title: "Launch URL")
    var launchURL: URL

    init() {}

    func perform() async throws -> some IntentResult {
        guard let parts = URLComponents(url: launchURL, resolvingAgainstBaseURL: false),
              let scheme = parts.scheme?.lowercased(),
              (scheme == "sidestore" || scheme == "livecontainer"
               || (scheme.hasPrefix("livecontainer")
                   && scheme.dropFirst("livecontainer".count).allSatisfy(\.isNumber))),
              (scheme == "sidestore" || parts.host?.lowercased() == "livecontainer-launch")
        else {
            throw NSError(domain: "ScarletCrystalLaunch", code: 1,
                          userInfo: [NSLocalizedDescriptionKey:
                                     "Expected a copied LiveContainer guest launch URL."])
        }
        await MainActor.run {
            // The existing LCTabView dispatchURL -> LCAppListView.handleURL
            // path handles the guest, requested container and JIT flag.
            UIApplication.shared.open(launchURL, options: [:], completionHandler: nil)
        }
        return .result()
    }
}
'''

BUILD_ID = "ABCD66000000000000000001"
FILE_ID = "ABCD66000000000000000002"
NAME = "ScarletCrystalLaunchAppIntent.swift"


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one project anchor, got {text.count(old)}: {old[:110]}")
    return text.replace(old, new, 1)


def patch(root: Path) -> None:
    source = root / "LiveContainer" / NAME
    project = root / "LiveContainer.xcodeproj" / "project.pbxproj"
    text = project.read_text()
    if "NRG_V66_FOUR_IDS" in text:
        if source.read_text() != SWIFT:
            raise RuntimeError("Existing V66 app intent does not match")
        return
    if source.exists():
        raise RuntimeError("Refusing to replace an unknown app intent source")
    text = once(
        text, "/* Begin PBXBuildFile section */",
        f"/* Begin PBXBuildFile section */\n"
        f"\t\t{BUILD_ID} /* {NAME} in Sources */ = "
        f"{{isa = PBXBuildFile; fileRef = {FILE_ID} /* {NAME} */; }}; // NRG_V66_FOUR_IDS")
    text = once(
        text, "/* Begin PBXFileReference section */",
        f"/* Begin PBXFileReference section */\n"
        f"\t\t{FILE_ID} /* {NAME} */ = "
        f"{{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
        f"path = {NAME}; sourceTree = \"<group>\"; }};")
    text = once(
        text, "\t\t\t\tE1292C032DCA3C160065E12D /* main.c */,",
        f"\t\t\t\t{FILE_ID} /* {NAME} */,\n"
        "\t\t\t\tE1292C032DCA3C160065E12D /* main.c */,")
    text = once(
        text, "\t\t\t\tE1292C132DCA46070065E12D /* main.c in Sources */,",
        f"\t\t\t\t{BUILD_ID} /* {NAME} in Sources */,\n"
        "\t\t\t\tE1292C132DCA46070065E12D /* main.c in Sources */,")
    source.write_text(SWIFT)
    project.write_text(text)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
