"""V17: screenshot/log-driven iPhone A/B relaunch and rotation guards.

Evidence: 2026-11-09 SourceCommit caa12a41e959 diagnostic,
legacy_fullscreen_launch_requested: multi_scene_unavailable.
These source contracts do not claim simultaneous in-memory iPhone sessions.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "HostApp/ScarletFullscreenGuestTab.swift").read_text()
HISTORY = (ROOT / "HostApp/ScarletGuestSessionLedger.swift").read_text()

class V17ColdSwitchRotation(unittest.TestCase):
    def test_cold_row_tap_is_actionable(self):
        start = GUEST.index("    private func switchTo(")
        end = GUEST.index("    // Draw the optical surface", start)
        code = GUEST[start:end]
        self.assertIn("guard target.canSwitch || target.canRelaunch else", code)
        self.assertIn("if onSwitch(target) {", code)
        self.assertIn("closePanel()", code)
        self.assertNotIn("이전 앱은 메모리에 없습니다. 앱 목록에서 다시 열 수", code)

    def test_original_lc_relaunch_uses_verified_installed_folder_and_container(self):
        code = GUEST.split("private static func switchGuest(to target:", 1)[1].split(
            "    @objc(installForGuestName:)", 1)[0]
        self.assertIn('target.id.hasSuffix(".app")', code)
        self.assertIn('let latest = installedApps().first(where:', code)
        self.assertIn("if latest.canSwitch, let container = latest.containerID", code)
        self.assertIn("guard latest.canRelaunch, let container = latest.containerID", code)
        self.assertIn('defaults.set(latest.id, forKey: "selected")', code)
        self.assertIn('defaults.set(container, forKey: "selectedContainer")', code)
        self.assertIn('defaults.string(forKey: "selected") == latest.id', code)
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(', code)
        self.assertIn('withClassicMode: latest.classicMode', code)
        self.assertIn('if !submitted {', code)
        self.assertIn('"memory": "not_preserved"', code)
        self.assertIn('switch_existing_multitask_session', code)
        self.assertIn('recentFolders.contains(folder)', GUEST)
        self.assertIn('Scarlet.Guest.RecentSessions.V14', HISTORY)

    def test_geometry_is_reconciled_without_ever_hiding_overlay(self):
        code = GUEST.split("private static func settleOverlayAfterRotation() {", 1)[1].split(
            "    // Use the host's real LC_HOME_PATH", 1)[0]
        self.assertIn("rotationWatchTask?.cancel()", code)
        self.assertIn("floatingWindow.alpha = 1", code)
        self.assertIn("placeFloatingWindow()", code)
        self.assertIn("overlay.alpha = 1", code)
        self.assertNotIn("overlay.alpha = 0", code)
        self.assertIn('"overlay_rotation_resumed"', code)
        self.assertIn("UIApplication.didBecomeActiveNotification", GUEST)
        self.assertIn("floatingWindow.frame = next", GUEST)
        self.assertIn('positionXKey', GUEST)
        self.assertIn('positionYKey', GUEST)
        self.assertIn('.position(x: screenButtonCenter.x, y: screenButtonCenter.y)', GUEST)

    def test_guest_switcher_still_uses_native_glass_with_readable_overlay(self):
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)', GUEST)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)', GUEST)
        self.assertIn('.clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))', GUEST)
        self.assertIn('SCARLET_PR48_AIRPODS_GLASS_PANEL', GUEST)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB', GUEST)
        self.assertNotIn('original.frame =', GUEST)
        self.assertNotIn('orientationLock =', GUEST)

if __name__ == "__main__":
    unittest.main()
