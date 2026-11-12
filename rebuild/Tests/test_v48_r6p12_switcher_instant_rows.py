"""R6P12: previously launched guest rows must not visually trail glass expansion.

Source-level regression only. Device first-frame paint/latency needs visual
capture; SwiftUI onAppear proves mounting, not completed display.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TAB = (ROOT / "HostApp/ScarletFullscreenGuestTab.swift").read_text()
STACK = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()


class ImmediateRecentRowsContract(unittest.TestCase):
    def test_recent_sessions_are_ready_before_panel_animation(self):
        opened = TAB.split("    private func openPanel() {", 1)[1].split(
            "    private func closePanel() {", 1)[0]
        self.assertLess(opened.index("apps = reloadApps()"),
                        opened.index("withAnimation(morphAnimation) { isOpen = true }"))
        self.assertIn('"switch_panel_sources_ready"', opened)
        self.assertIn('"elapsed_ms"', opened)
        self.assertIn('onPanel(true, apps.count)', opened)

    def test_eager_rows_without_second_fade(self):
        content = TAB.split("    private var appPanelContent: some View {", 1)[1].split(
            "    private var appPanel: some View", 1)[0]
        self.assertIn("VStack(alignment: .leading, spacing: 12)", content)
        self.assertNotIn("LazyVStack(", content)
        self.assertIn("ForEach(otherApps) { entry in otherAppRow(entry) }", content)
        self.assertIn('"switch_panel_recent_rows_mounted"', content)
        self.assertIn(".transition(.identity)", content)
        self.assertIn(".transaction { $0.disablesAnimations = true }", content)
        self.assertNotIn(".transition(.opacity)", content)
        self.assertNotIn("DispatchQueue.main.asyncAfter", content)

    def test_native_glass_and_guest_viewport_unchanged(self):
        # The fixed destination and original glass morph remain intact.
        self.assertIn("glassPlate(radius: isOpen ? 28 : 31)", TAB)
        self.assertIn("Animation.spring(response: 0.45, dampingFraction: 0.88)", TAB)
        self.assertIn("withAnimation(morphAnimation) { isOpen = true }", TAB)
        self.assertIn(".position(x: geometry.size.width / 2,", TAB)
        self.assertIn("ScarletGuestRoundTabCenterXFractionV1", TAB)
        self.assertIn("slots.map { slot in", STACK)
        self.assertIn("return targets", STACK)
        self.assertIn("ScarletFullscreenGuestTabInstaller.makeResidentSwitcherWindow", STACK)


if __name__ == "__main__":
    unittest.main()
