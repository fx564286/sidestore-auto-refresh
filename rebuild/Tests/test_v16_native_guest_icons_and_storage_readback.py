"""V16: guest switcher artwork and durable A/B history readback guards."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "HostApp/ScarletGuestSwitcherOverlay.swift").read_text()
FULL = (ROOT / "HostApp/ScarletFullscreenGuestTab.swift").read_text()
LEDGER = (ROOT / "HostApp/ScarletGuestSessionLedger.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()

class V16NativeGuestRegression(unittest.TestCase):
    def test_native_guest_rows_show_installed_app_icons(self):
        self.assertIn("enum ScarletGuestIconCatalog", NATIVE)
        self.assertIn("ScarletGuestIconCatalog.icon(forFolder: folder)", FULL)
        self.assertIn("ScarletGuestIconCatalog.icon(for: item, history: history)", NATIVE)
        self.assertIn("Image(uiImage: icon)", NATIVE)
        self.assertIn('SCARLET_GUEST_APP_ICON', NATIVE)
        self.assertIn('LCAppIconLight.png', NATIVE)
        self.assertIn('CFBundlePrimaryIcon', NATIVE)
        self.assertIn('CFBundleIconFiles', NATIVE)
        self.assertIn('!folder.contains("/")', NATIVE)
        self.assertIn('!folder.contains("\\\\")', NATIVE)
        self.assertIn("guestIcons.removeAll(keepingCapacity: false)", NATIVE)
        self.assertNotIn('UIImage(named:', NATIVE)

    def test_both_guest_overlays_stay_closed_until_tap(self):
        self.assertIn("@State private var isOpen = false", NATIVE)
        self.assertIn("@State private var isOpen = false", FULL)
        self.assertIn("if isOpen {", NATIVE)
        self.assertIn("if isOpen {", FULL)

    def test_a_b_ledger_written_before_handoff_with_readback(self):
        self.assertLess(
            HOST.index('ScarletGuestSessionLedger.noteLaunch('),
            HOST.index('try await app.runApp()')
        )
        self.assertIn("ScarletGuestSessionLedger.recent()", NATIVE)
        self.assertIn("store.data(forKey: key) == encoded", LEDGER)
        self.assertIn('"readback": persisted ? "persisted" : "failed"', LEDGER)
        self.assertIn('ScarletGuestSessionLedger.restore(historyBeforeLaunch)', HOST)

    def test_cold_rows_never_claim_ram_was_kept(self):
        self.assertIn('guard item.isLive else', NATIVE)
        self.assertIn('app.canSwitch ? "실행 중 · 작업 유지" : "최근 실행 · 재시작 필요"', FULL)
        self.assertIn('ScarletGuestSceneRegistry.activate(item.id)', NATIVE)

if __name__ == "__main__":
    unittest.main()
