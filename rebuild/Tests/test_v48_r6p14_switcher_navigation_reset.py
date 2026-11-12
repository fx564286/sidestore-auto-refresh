"""R6P14: close switcher before navigation; do not carry expansion across guests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TAB = (ROOT / "HostApp/ScarletFullscreenGuestTab.swift").read_text()
STACK = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()


class SwitcherNavigationReset(unittest.TestCase):
    def test_switch_closes_before_scene_selection_and_reopens_on_rejection(self):
        body = TAB.split("    private func switchTo(", 1)[1].split(
            "    // Native optical surface", 1)[0]
        self.assertIn("closePanel()\n        if onSwitch(target)", body)
        self.assertIn("openPanel()\n            feedback =", body)

    def test_home_button_closes_panel_before_invoking_exit(self):
        body = TAB.split('Label("앱 목록"', 1)[0].rsplit(
            '"fullscreen_tab_exit_requested")', 1)[1]
        self.assertIn("closePanel()\n                    onExit()", body)

    def test_close_is_idempotent_and_native_hit_testing_resets_immediately(self):
        body = TAB.split("    private func closePanel() {", 1)[1].split(
            "    private func switchTo(", 1)[0]
        self.assertIn("guard isOpen else { return }", body)
        self.assertLess(body.index("onPanel(false, apps.count)"),
                        body.index("withAnimation(morphAnimation) { isOpen = false }"))

    def test_external_navigation_resets_retained_switcher_state(self):
        method = STACK.split("private func collapseSwitcherForNavigation(", 1)[1].split(
            "    func enqueueSignedGuest(", 1)[0]
        self.assertIn("overlayWindow.dismissState?.requestClose()", method)
        self.assertIn("overlayWindow.isExpanded = false", method)
        self.assertIn('"switch_panel_navigation_reset"', method)
        for transition in ("go_home", "activate_guest", "enqueue_guest"):
            self.assertIn(f'collapseSwitcherForNavigation("{transition}")', STACK)

    def test_glass_morph_geometry_and_live_guest_retention_unchanged(self):
        self.assertIn("Animation.spring(response: 0.45, dampingFraction: 0.88)", TAB)
        self.assertIn("glassPlate(radius: isOpen ? 28 : 31)", TAB)
        self.assertIn("viewport?.pauseAllResidentAudioOnHome()", STACK)
        self.assertIn('"retained_until_pid_exits"', STACK)


if __name__ == "__main__":
    unittest.main()
