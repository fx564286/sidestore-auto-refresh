"""V80: preserve native launch error and allow one safe pre-dispatch read retry."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HANDLER = ROOT / "scripts/templates/combined_refresh_handler.swift"
BRIDGE = ROOT / "scripts/templates/v3_service_bridge.swift"

class V80LaunchRecoveryTests(unittest.TestCase):
    def test_native_launch_callback_separates_native_error_missing_id_and_pid(self):
        source = HANDLER.read_text(encoding="utf-8")
        begin = source.index("    private func launchEmbeddedSideStore")
        end = source.index("    fileprivate func accepted(", begin)
        block = source[begin:end]
        self.assertIn("SCARLET_V80_EXTENSION_LAUNCH", block)
        for event in ("event=request_cancelled", "event=request_interrupted",
                      "missing_request_identifier", "native_launch_error",
                      "event=missing_launched_pid"):
            self.assertIn(event, block)
        self.assertIn("self.failed(id, stage: .extensionLaunch, underlying: error)", block)
        self.assertIn("guard self.launchID == id else", block)
        self.assertIn("guard self.launchRequestPending == id else { return }", block)
        self.assertIn("self.service.signal(.launched, attempt: id)", block)
        self.assertIn("self.confirmLaunchedPeer(id)", block)

    def test_read_retry_happens_before_xpc_dispatch(self):
        source = BRIDGE.read_text(encoding="utf-8")
        req_start = source.index("    public func request(operation:")
        pending = source.index("pending[id] = continuation", req_start)
        retry = source.index("SCARLET_V80_SNAPSHOT_LAUNCH_RECOVERY", req_start)
        self.assertLess(retry, pending, "retry must only run before request XPC dispatch")
        self.assertEqual(source.count("SCARLET_V80_SNAPSHOT_LAUNCH_RECOVERY"), 1)
        block = source[retry:source.index("            if let connectedTicket",retry)]
        self.assertEqual(block.count("try await connect()"), 2)
        self.assertIn('failure.operation == "connect"', block)
        self.assertIn("failure.stage == .extensionLaunch", block)
        self.assertIn("(failure.code == .failed || failure.code == .interrupted)", block)
        self.assertIn('(operation == "snapshot" || operation == "settingsGet")', block)
        self.assertIn("V3WireContract.readOperations.contains(operation)", block)
        self.assertIn("try await Task.sleep(nanoseconds: 300_000_000)", block)
        self.assertEqual(block.count("try Task.checkCancellation()"), 2)
        self.assertIn("else { throw error }", block)

    def test_original_connect_error_and_request_id_preserved_after_retry_failure(self):
        source = BRIDGE.read_text(encoding="utf-8")
        start = source.index("SCARLET_V80_SNAPSHOT_LAUNCH_RECOVERY")
        end = source.index("        let isBoundedSessionCreation", start)
        block = source[start:end]
        self.assertIn("} catch {", block)
        self.assertIn("let annotated = V3CatalogRequestContext.annotating(error, requestedOperation: operation, requestID: id)", block)
        self.assertIn("if error is CancellationError { throw CancellationError() }", block)
        self.assertIn("throw annotated", block)
        self.assertNotIn("statusDispatchedRequestIDs.insert", block)

    def test_no_native_error_details_or_persistent_state_changed(self):
        source = HANDLER.read_text(encoding="utf-8")
        section = source[source.index("// SCARLET_V80_EXTENSION_LAUNCH"):source.index("    fileprivate func accepted(")]
        for forbidden in ("error.localizedDescription", "error.userInfo", "error.domain",
                          "UserDefaults.standard", "mobileprovision", "privateKey"):
            self.assertNotIn(forbidden, section)
        # Ensure existing callback and retirement identity fence still operates.
        for required in ("retiringRequestPending = id", "ext._kill(9)",
                         "self.retiringRequestPending = nil", "self.launchID == id"):
            self.assertIn(required, source)

if __name__ == "__main__":
    unittest.main()
