"""V47 new structure: direct native scene handoff, no host detour.

Source contracts, not a claim that iOS retains a scene in the field.
"""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCENE = (ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
TAB = (ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
HOST = (ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
WORKFLOW = (ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class TestV47InPlaceGuestSwitch(unittest.TestCase):
    def test_live_guest_takes_direct_route_without_host(self):
        code=SCENE[SCENE.index('private func switchOrLaunch('):SCENE.index('func activate(folder:')]
        self.assertIn('if target.canSwitch',code)
        self.assertIn('activate(folder: target.id)',code)
        self.assertIn('fullscreen_scene_direct_switch',code)
        self.assertIn('"same_pid_scene_selected"',code)
        self.assertNotIn('launchToGuestApp(',code)
        self.assertNotIn('openWindow(',code)

    def test_new_guest_signs_then_queues_inside_resident_stack(self):
        code=SCENE[SCENE.index('private func switchOrLaunch('):SCENE.index('func activate(folder:')]
        self.assertIn('try await model.signApp(force: false)',code)
        self.assertIn('try self.enqueueSignedGuest(model)',code)
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(',code)
        self.assertIn('ScarletGuestSessionLedger.restore(earlier)',code)
        self.assertIn('pendingInPlaceLaunch = true',code)
        self.assertIn('pendingInPlaceLaunch = false',code)
        self.assertIn('fullscreen_scene_inplace_launch_failed',code)

    def test_normal_panel_only_shows_launched_apps(self):
        self.assertIn('let launched = apps.filter { !$0.isCurrent }',TAB)
        self.assertIn('return launched.filter { $0.reason != "inplace_first_launch" }',TAB)
        self.assertIn('apps.filter { $0.reason == "inplace_first_launch" }',TAB)
        self.assertIn('showingInstallChoices = false',TAB)
        self.assertIn('if showingInstallChoices {',TAB)
        self.assertIn('SCARLET_RESIDENT_GUEST_ADD_INLINE',TAB)
        self.assertIn('let installedApps: [LCAppModel]',SCENE)
        self.assertIn('installedApps: sharedModel.apps',HOST)

    def test_live_process_never_disappears_during_new_scene_bootstrap(self):
        self.assertIn('vc.view.layer.opacity = 0',SCENE)
        self.assertIn('vc.view.isUserInteractionEnabled = false',SCENE)
        self.assertIn('fullscreen_scene_first_surface_revealed',SCENE)
        self.assertIn('slots[index].pid = vc.pid',SCENE)
        self.assertIn('revealStartedScene(slots[index].id)',SCENE)
        self.assertIn('if ready, viewport?.select(folder: folder) == true',SCENE)
        self.assertIn('attemptsRemaining > 0',SCENE)
        self.assertIn('guard !old.isAppRunning else { return false }',SCENE)
        self.assertIn('old.view.removeFromSuperview()',SCENE)
        self.assertNotIn('terminate()',SCENE)

    def test_safe_area_and_signed_release_contract(self):
        self.assertIn('first(where: { $0.isKeyWindow })?.safeAreaInsets',SCENE)
        self.assertIn('fullscreen_scene_host_safe_area',SCENE)
        self.assertIn('.statusBarHidden(false)',HOST)
        self.assertIn('experimentalFullscreenResident = false',HOST)
        self.assertIn('Scarlet-Crystal-V47-UNSIGNED.ipa',WORKFLOW)
        self.assertIn('scarlet-v47-unsigned-20261111',WORKFLOW)

if __name__ == '__main__': unittest.main()
