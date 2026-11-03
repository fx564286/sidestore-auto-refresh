#!/usr/bin/env python3
"""Forward-port the original Scarlet refresh bridge onto latest LiveContainer.

SideStoreSupport and LiveContainerSwiftUI are distinct Swift modules; both
must compile an identical copy of V3SharedAppGroup. The old fixed-source V3
overlay added the scheduled entry point, but its September source pin is
not valid on October's official LiveContainer. Add only the missing entry
point without replacing upstream startRefresh or changing user credentials.
"""
from pathlib import Path
import sys

MARKER = "SCARLET_V179_LATEST_UPSTREAM_SCHEDULED_REFRESH"

REFRESH_COMPAT = """// SCARLET_V179_LATEST_UPSTREAM_SCHEDULED_REFRESH
import Foundation

// The public upstream RefreshHandler still implements startRefresh.
// Preserve it. This adapter only binds the scheduler's recorded runID
// to the same entitled App Group store used by the embedded service.
extension RefreshHandler {
    func startScheduledRefresh(identifier: String, mangledName: String,
                               runID: String) async throws {
        guard UUID(uuidString: runID) != nil else {
            throw NSError(domain: "ScarletCrystal.Refresh", code: 2,
                          userInfo: [NSLocalizedDescriptionKey:
                            "The scheduled refresh run identifier is invalid."])
        }
        let defaults = try V3SharedAppGroup.requireSharedUserDefaults()
        defaults.set(runID, forKey: "liveContainerAutoRefreshExpectedRunID")
        try await startRefresh(identifier: identifier, mangledName: mangledName)
    }
}
"""


def patch(root, template):
    support = root / "SideStoreSupport"
    swift = support / "SideStore.swift"
    bridge = support / "ScarletV179RefreshCompatibility.swift"
    app_group = support / "V3SharedAppGroup.swift"
    main_shared = root / "LiveContainerSwiftUI/Utilities/V3SharedAppGroup.swift"
    if not swift.exists() or not main_shared.exists():
        raise ValueError("Scarlet host overlay must be applied before refresh compatibility")
    if "class RefreshHandler" not in swift.read_text():
        raise ValueError("upstream RefreshHandler definition unavailable")
    if "func startScheduledRefresh(" in swift.read_text():
        raise ValueError("upstream now implements scheduled refresh; re-review before adding adapter")
    body = template.read_text()
    if body != main_shared.read_text():
        raise ValueError("host/shared AppGroup sources differ; refusing split identity")
    if app_group.exists() and app_group.read_text() != body:
        raise ValueError("existing SideStoreSupport App Group implementation differs")
    if bridge.exists() and bridge.read_text() != REFRESH_COMPAT:
        raise ValueError("different refresh bridge already exists; cannot overwrite")
    if not app_group.exists():
        app_group.write_text(body)
    if not bridge.exists():
        bridge.write_text(REFRESH_COMPAT)
    result = app_group.read_text() == main_shared.read_text() and MARKER in bridge.read_text()
    if not result:
        raise ValueError("refresh compatibility adapter verification failed")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v179_refresh_compat.py <LiveContainer checkout>")
    root = Path(sys.argv[1]).resolve()
    template = Path(__file__).resolve().parent / "templates/v3_shared_app_group.swift"
    patch(root, template)
    print("[PASS] latest LiveContainer scheduled refresh adapter and matched entitled group in both targets")


if __name__ == "__main__":
    main()
