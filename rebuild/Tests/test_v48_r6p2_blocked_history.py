"""R6P2: blocked resident guests must never enter the running-app switcher.

Source-contract regression only; on-device switching and launch need a device
log with a successful process/scene acknowledgment.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()


class BlockedResidentHistoryTests(unittest.TestCase):
    def test_blocked_guest_restores_provisional_history(self):
        method = HOST.split("    private func runGuest(_ key: String) {", 1)[1]
        provisional = method.split("ScarletGuestSessionLedger.noteLaunch(", 1)[1]
        self.assertIn("session_history_pre_handoff", provisional)
        blocked = method.split(
            "if residentSessionActive && experimentalFullscreenResident {", 1
        )[1].split("if !experimentalFullscreenResident {", 1)[0]
        restoration = blocked.index(
            "ScarletGuestSessionLedger.restore(historyBeforeLaunch)"
        )
        denial = blocked.index("resident_incompatible_launch_blocked")
        self.assertLess(restoration, denial)
        self.assertIn("blocked_launch_history_reverted", blocked)
        self.assertIn('"count": String(ScarletGuestSessionLedger.recent().count)', blocked)
        self.assertIn('requires_original_lc_runtime', blocked)

    def test_valid_path_keeps_original_ram_and_geometry_handling(self):
        self.assertIn("fullscreenStack.activate(folder: folder)", HOST)
        self.assertIn("fullscreenStack.enqueueSignedGuest(app)", HOST)
        self.assertIn("try await app.runApp(multitask: false)", HOST)


if __name__ == "__main__":
    unittest.main()
