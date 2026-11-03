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
    @MainActor
    func startScheduledRefresh(identifier: String, mangledName: String,
                               runID: String) async throws {
        guard UUID(uuidString: runID) != nil else {
            throw NSError(domain: "ScarletCrystal.Refresh", code: 2,
                          userInfo: [NSLocalizedDescriptionKey:
                            "The scheduled refresh run identifier is invalid."])
        }
        guard v3RefreshToken == nil else {
            throw NSError(domain: "ScarletCrystal.Refresh", code: 4,
                          userInfo: [NSLocalizedDescriptionKey:
                            "Another verified refresh run owns the service."])
        }
        let token = UUID().uuidString
        v3RefreshToken = token
        v3RefreshAdmissionRunID = runID
        defer {
            if v3RefreshToken == token {
                v3RefreshToken = nil
                v3RefreshAdmissionRunID = nil
            }
        }
        let defaults = try V3SharedAppGroup.requireSharedUserDefaults()
        defaults.set(runID, forKey: "liveContainerAutoRefreshExpectedRunID")
        try await startRefresh(identifier: identifier, mangledName: mangledName)
    }
}
"""


def patch_v181_refresh_service_lifecycle(source):
    """Carry the original LiveProcess/XPC launch handshake into the V3 host.

    Do not fake an existing connection and never trigger Refresh All merely
    to establish the command channel. Keep the original refresh path intact.
    """
    mark = "SCARLET_V181_REFRESH_SERVICE_LIFECYCLE"
    if mark in source:
        required = ("func ensureServiceConnected() async throws",
                    "func v3_stopService()",
                    "var v3RefreshToken: String?",
                    "var v3ServiceIdentity: UUID")
        if any(token not in source for token in required):
            raise ValueError("partial V181 refresh service host bridge")
        return source
    begin = "        if listener == nil {\n"
    finish = "        guard let client = self.client else {\n"
    if source.count(begin) != 1 or source.count(finish) != 1:
        raise ValueError("latest native refresh launch path drifted")
    start = source.index(begin)
    end = source.index(finish, start)
    original_launch = source[start:end]
    # A connection-only entrypoint must *throw* for unavailable listener or
    # missing extension rather than quietly claiming it is connected.
    original_launch = original_launch.replace(
        "                return\n",
        "                throw NSError(domain: \"ScarletCrystal.Connection\", code: 1)\n")
    original_launch = original_launch.replace(
        "            return\n",
        "            throw NSError(domain: \"ScarletCrystal.Connection\", code: 1)\n")
    if "        let uuid = await ext.beginRequest" not in original_launch:
        raise ValueError("upstream SideStore launch handshake incomplete")
    # The extracted upstream block contains whitespace-only lines. Normalize
    # those copied lines so git diff --check accepts the generated adapter.
    original_launch = "\n".join(line.rstrip(" \t") for line in original_launch.split("\n"))
    extra = """
    // SCARLET_V181_REFRESH_SERVICE_LIFECYCLE:
    // ownership corresponds to the actual live guest process, not an
    // optimistic persisted pairing or a completed XPC request.
    var v3RefreshToken: String? = nil
    var v3RefreshAdmissionRunID: String? = nil
    var v3ServiceIdentity: UUID = UUID()

    @MainActor
    func ensureServiceConnected() async throws {
        if sideStorePid > 0 && getpgid(sideStorePid) > 0 {
            guard client != nil else {
                throw NSError(domain: "ScarletCrystal.Connection", code: 2)
            }
            return
        }
        v3ServiceIdentity = UUID()
        client = nil
""" + original_launch + """
        guard client != nil, sideStorePid > 0 && getpgid(sideStorePid) > 0 else {
            throw NSError(domain: "ScarletCrystal.Connection", code: 3)
        }
    }

    @MainActor
    func v3_stopService() {
        // Caller must first establish an explicit retirement decision.
        // Never delete the paired device record, certificates, or accounts.
        if let c { c.resume(throwing: CancellationError()); self.c = nil }
        if let launchContinuation {
            launchContinuation.resume(throwing: CancellationError())
            self.launchContinuation = nil
        }
        ext?._kill(9)
        ext = nil
        client = nil
        listener?.invalidate()
        listener = nil
        sideStorePid = 0
        v3RefreshToken = nil
        v3RefreshAdmissionRunID = nil
        v3ServiceIdentity = UUID()
    }
"""
    needle = "    func updateProgress(_ value: Double) {\n"
    if source.count(needle) != 1:
        raise ValueError("current native RefreshHandler body changed")
    return source.replace(needle, extra + "\n" + needle, 1)


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
    current_service = swift.read_text()
    updated_service = patch_v181_refresh_service_lifecycle(current_service)
    if patch_v181_refresh_service_lifecycle(updated_service) != updated_service:
        raise ValueError("non-idempotent latest V181 refresh service lifecycle")
    if updated_service != current_service:
        swift.write_text(updated_service)

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

    # V3ShortcutRefreshRequest was defined in the old full V3 overlay,
    # which cannot be applied wholesale to the latest two upstream trees.
    # Extract its exact tested request/correlation declarations for both
    # independent Swift modules: the host receives and SideStoreSupport sends.
    primitive_file = Path(__file__).resolve().parent / "templates/v3_behavioral_primitives.swift"
    primitive = primitive_file.read_text()
    begin = "public struct V3ShortcutRefreshRequest: Equatable {"
    finish = "\nenum V3RefreshIntentStartPolicy {"
    if primitive.count(begin) != 1 or primitive.count(finish) != 1:
        raise ValueError("canonical V3 request declarations changed")
    request_types = "import Foundation\n\n" + primitive[
        primitive.index(begin):primitive.index(finish)
    ] + "\n"
    host_request = root / "LiveContainerSwiftUI/Utilities/V3ShortcutRefreshRequest.swift"
    support_request = support / "V3ShortcutRefreshRequest.swift"
    for request_file in (host_request, support_request):
        if request_file.exists() and request_file.read_text() != request_types:
            raise ValueError(f"conflicting V3 request contract: {request_file}")
        if not request_file.exists():
            request_file.write_text(request_types)

    # Restore the canonical typed failure vocabulary used by the scheduler.
    # This is the same fully-defined contract from the older Scarlet overlay,
    # not a fabricated placeholder or an untyped NSError fallback.
    canonical_failure = Path(__file__).resolve().parent / "templates/combined_failure.swift"
    failure_file = root / "LiveContainerSwiftUI/Utilities/CombinedFailure.swift"
    failure_body = canonical_failure.read_text()
    if "public struct CombinedFailure: Error, LocalizedError {" not in failure_body:
        raise ValueError("canonical CombinedFailure contract unavailable")
    if failure_file.exists() and failure_file.read_text() != failure_body:
        raise ValueError("different failure contract already exists in host")
    if not failure_file.exists():
        failure_file.write_text(failure_body)

    # SideStoreSupport is its own Swift module. Both the host and embedded
    # refresh bridge use the same typed failure vocabulary, but SwiftUI's
    # internal source file cannot satisfy SideStoreSupport compilation.
    support_failure = support / "CombinedFailure.swift"
    if support_failure.exists() and support_failure.read_text() != failure_body:
        raise ValueError("conflicting typed failure contract in SideStoreSupport")
    if not support_failure.exists():
        support_failure.write_text(failure_body)

    # The scheduler also requires the real direct-run ownership policy.
    direct_start = "enum V3DirectRefreshRunClaimPolicy {"
    direct_end = "\nenum V3RequestRetirementPolicy {"
    if primitive.count(direct_start) != 1 or primitive.count(direct_end) != 1:
        raise ValueError("canonical direct-run ownership declaration changed")
    direct_body = "import Foundation\n\n" + primitive[
        primitive.index(direct_start):primitive.index(direct_end)
    ] + "\n"
    direct_file = root / "LiveContainerSwiftUI/Utilities/V3DirectRefreshRunClaimPolicy.swift"
    if direct_file.exists() and direct_file.read_text() != direct_body:
        raise ValueError("different direct-run ownership code already exists in host")
    if not direct_file.exists():
        direct_file.write_text(direct_body)

    # Preserve the scheduler's terminal-state and pairing-admission
    # policies exactly as supplied by the older tested fork. These are
    # needed by the generated latest-upstream host UI and have no external
    # UI/transport dependencies.
    host_utilities = root / "LiveContainerSwiftUI/Utilities"
    primitives = (
        ("V3RefreshTerminalRecoveryPolicy.swift",
         "enum V3RefreshTerminalRecoveryPolicy {",
         "\nstruct V3RefreshRunIdentitySelection: Equatable {"),
        ("V3RefreshPrerequisites.swift",
         "enum V3RefreshPrerequisiteState: String, Equatable {",
         "\nenum V3IssueActionOutcomePolicy {"),
    )
    for file_name, first, last in primitives:
        if primitive.count(first) != 1 or primitive.count(last) != 1:
            raise ValueError("required V3 policy contract changed: " + file_name)
        exact = "import Foundation\n\n" + primitive[
            primitive.index(first):primitive.index(last)
        ] + "\n"
        destination = host_utilities / file_name
        if destination.exists() and destination.read_text() != exact:
            raise ValueError("conflicting tested V3 refresh policy: " + file_name)
        if not destination.exists():
            destination.write_text(exact)

    # The original V3UnifiedShell owns the typed v3StatusStore environment key.
    # Do not generate the obsolete V179 placeholder with the same property.
    # It changes the type and produces invalid Swift redeclarations.

    result = (app_group.read_text() == main_shared.read_text()
              and MARKER in bridge.read_text()
              and host_request.read_text() == support_request.read_text()
              and failure_file.read_text() == failure_body
              and support_failure.read_text() == failure_body
              and direct_file.read_text() == direct_body
              and "V3RefreshRunCorrelation" in host_request.read_text())
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
