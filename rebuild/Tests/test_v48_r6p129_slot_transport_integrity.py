"""R6P129 native slot response bounds, typed result fidelity and readback serialization."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = (ROOT / "HostApp/ScarletAuthXPCSupport.swift").read_text()
WORKER = (ROOT / "integration/ScarletDeviceInstallAgent.swift.txt").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
LIST = SUPPORT.split("public enum ScarletNativeSideloadSlots", 1)[1].split("public static func change", 1)[0]
CHANGE = SUPPORT.split("public enum ScarletNativeSideloadSlots", 1)[1].split("public static func change", 1)[1].split("private final class ScarletSlotsListGate", 1)[0]
SHEET = HOST.split("private struct ScarletManagedSlotSheet:", 1)[1].split("// R6P61_SLOT_MANAGER_END", 1)[0]

class SlotTransportIntegrity(unittest.TestCase):
    def test_worker_errors_are_not_masked_and_unknown_success_is_rejected(self):
        for reason in ("team_operation_in_progress", "selected_account_owner_unverified"):
            self.assertIn(reason, LIST)
            self.assertIn(reason, CHANGE)
        self.assertIn("selected_account_app_mismatch", CHANGE)
        self.assertIn("ok == successReasons.contains(status)", CHANGE)
        self.assertIn('gate.finish(false, "worker_unknown")', CHANGE)

    def test_only_successful_well_formed_lists_publish_rows(self):
        self.assertIn("guard successReasons.contains(status) else", LIST)
        self.assertIn("guard let raw = json", LIST)
        self.assertIn("Set(rows.map(\\.id)).count == rows.count", LIST)
        self.assertIn("rows.allSatisfy", LIST)

    def test_worker_uses_utf8_budget_and_shared_row_limit(self):
        listing = WORKER.split("static func listManagedSlots(", 1)[1].split("@objc(setManagedSlot:", 1)[0]
        self.assertIn("slotDisplayName(app.name)", listing)
        self.assertEqual(listing.count("slotDisplayName(app.name)"), 2)
        self.assertIn("rows.count <= 80", listing)
        self.assertIn("Set(rows.map(\\.id)).count == rows.count", listing)
        self.assertIn("String(character).utf8.count", WORKER)
        self.assertIn("byteCount + size <= 120", WORKER)

    def test_operation_holds_ui_lock_until_authoritative_readback(self):
        change = SHEET.split("private func change(", 1)[1]
        self.assertIn("guard !loading && !operationRunning", change)
        self.assertIn("defer { operationRunning = false }", change)
        self.assertNotIn("\n        operationRunning = false\n", change)
        self.assertIn("rows = after.apps", change)
        self.assertIn('after.reason != "ready"', change)
        self.assertIn("$0.active != active", change)

    def test_distinct_release(self):
        wf = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()
        self.assertIn("fix/scarlet-r6p129-slot-transport-integrity-20261124", wf)
        self.assertIn("SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.129)", wf)
        self.assertEqual(wf.count("Scarlet-Crystal-V48-R6P129-SLOT-TRANSPORT-INTEGRITY-UNSIGNED.ipa"), 2)

if __name__ == "__main__":
    unittest.main()
