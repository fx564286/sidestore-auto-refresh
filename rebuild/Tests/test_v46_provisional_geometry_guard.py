"""Regression: never apply a provisional SwiftUI safe-area frame to live scenes."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
S = (ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
HOST = (ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()

class V46FullscreenGuard(unittest.TestCase):
    def test_validate_before_resizing_any_guest(self):
        start = S.index('override func viewDidLayoutSubviews()')
        end = S.index('func isAlive(folder:', start)
        layout = S[start:end]
        guard = layout.index('abs(expected.width - actual.width) < 2')
        rejected_return = layout.index('return\n        }', guard)
        resize = layout.index('vc.view.frame = slot')
        self.assertLess(guard, rejected_return)
        self.assertLess(rejected_return, resize)
        self.assertIn('lastRejectedBounds != actual', layout)
        self.assertIn('fullscreen_scene_geometry_applied', layout)
        self.assertIn('settings.setFrame(slot)', layout)
        self.assertIn('abs(chromeTop - lastChromeTop)', layout)
        self.assertIn('settings.setInterfaceOrientation(orientation)', layout)

    def test_no_guest_view_or_original_design_removed(self):
        self.assertIn('controllers[slot.id] = vc', S)
        self.assertIn('view.addSubview(vc.view)', S)
        self.assertIn('vc.scaleRatio = 1', S)
        self.assertNotIn('CGAffineTransform', S)
        self.assertIn('guard !old.isAppRunning else { return false }', S)
        self.assertIn('experimentalFullscreenResident = false', HOST)
        self.assertIn('try await app.runApp(multitask: false)', HOST)

if __name__ == '__main__': unittest.main()
