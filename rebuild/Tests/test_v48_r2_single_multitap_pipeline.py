"""V48-R2: unify multitasking UI/drag in resident and original guest modes.
Source contracts; phone touch and RAM retention require a real device test.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
TAB=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
SCENE=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
W=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class SingleSwitcher(unittest.TestCase):
    def test_one_native_window_factory_for_both_modes(self):
        self.assertEqual(TAB.count('enum ScarletGuestSwitcherWindowFactory {'),1)
        self.assertEqual(TAB.count('let overlay = ScarletGuestTouchPassthroughWindow(windowScene: scene)'),1)
        self.assertEqual(TAB.count('overlay.enableUnifiedHoldToDrag()'),1)
        self.assertEqual(TAB.count('let content = ScarletFullscreenGuestFloatingTab('),1)
        self.assertIn('ScarletGuestSwitcherWindowFactory.make(',TAB)
        self.assertIn('ScarletGuestSwitcherWindowFactory.make(',SCENE)
        self.assertNotIn('window.rootViewController = UIHostingController(',SCENE)
        self.assertNotIn('UIPanGestureRecognizer(',TAB)
        self.assertNotIn('UILongPressGestureRecognizer(',SCENE)

    def test_hold_move_and_shared_position(self):
        self.assertIn('let hold = UILongPressGestureRecognizer(',TAB)
        self.assertIn('hold.minimumPressDuration = 0.38',TAB)
        self.assertIn('hold.allowableMovement = 18',TAB)
        self.assertIn('addGestureRecognizer(hold)',TAB)
        self.assertIn('guard !isExpanded, gestureRecognizer === holdGesture else { return false }',TAB)
        self.assertIn('synchronizeButtonCenter(CGPoint(',TAB)
        self.assertIn('ScarletGuestFloatingDockChanged',TAB)
        self.assertIn('floating_tab_hold_started',TAB)
        self.assertIn('floating_tab_position_saved',TAB)
        self.assertIn('ScarletGuestRoundTabCenterXFractionV1',TAB)
        self.assertIn('ScarletGuestRoundTabCenterYFractionV1',TAB)
        self.assertIn('savedCenter(fallback: center)',TAB)
        self.assertIn('center: center(in: original)',TAB)
        self.assertIn('overlayWindow?.frame = scene.coordinateSpace.bounds',SCENE)
        self.assertNotIn('vc.scaleRatio = 0.',SCENE)

    def test_no_app_add_branch_any_mode(self):
        for fragment in ('showingInstallChoices','installChoices',
                         'SCARLET_RESIDENT_GUEST_ADD_INLINE','Label("앱 추가"',
                         'inplace_first_launch'):
            self.assertNotIn(fragment,TAB)
            self.assertNotIn(fragment,SCENE)
        self.assertIn('slots.map { slot in',SCENE)
        self.assertIn('apps.filter { !$0.isCurrent }',TAB)
        self.assertIn('Label("앱 목록"',TAB)
        self.assertIn('onExit: { [weak self] in self?.goHome() }',SCENE)
        self.assertIn('LCSharedUtils.launchToGuestApp(withClassicMode: 0)',TAB)

    def test_baseline_preserved_and_versioned_ipa(self):
        self.assertIn('if experimentalFullscreenResident || fullscreenStack.hasResidentSession',HOST)
        self.assertIn('try await app.runApp(multitask: false)',HOST)
        self.assertIn('Scarlet-Crystal-V48-R2-UNSIGNED.ipa',W)
        self.assertIn('scarlet-v48-r2-unsigned-20261111',W)

if __name__ == '__main__': unittest.main()
