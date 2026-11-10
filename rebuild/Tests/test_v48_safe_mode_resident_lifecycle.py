"""V48 prevents simultaneous LC runtimes and restores original fullscreen status bar policy.
Source contracts; no claim of an on-device pass.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
S=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
I=(R/'integration/apply_scarlet_host.py').read_text()
T=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class TestV48(unittest.TestCase):
 def test_mode_change_cannot_mix_legacy_with_running_liveprocess(self):
  self.assertIn('let residentSessionActive = fullscreenStack.hasResidentSession',H)
  self.assertIn('experimentalFullscreenResident || residentSessionActive',H)
  self.assertIn('resident_incompatible_launch_blocked',H)
  self.assertIn('.disabled(fullscreenStack.hasResidentSession)',H)
  self.assertIn('resident_mode_change_deferred',H)
  self.assertLess(H.index('resident_incompatible_launch_blocked'),H.index('try await app.runApp(multitask: false)'))
 def test_live_open_skips_resign_and_relaunch(self):
  part=H[H.index('if (experimentalFullscreenResident || residentSessionActive)'):H.index('native_multiscene_launch_requested')]
  self.assertLess(part.index('fullscreenStack.livePID(folder: folder)'),part.index('try await app.signApp(force: false)'))
  self.assertIn('fullscreen_scene_reopened_without_resign',part)
  self.assertIn('fullscreenStack.activate(folder: folder)',part)
 def test_dead_guest_relaunch_releases_only_dead_controller(self):
  self.assertIn('guard !old.isAppRunning else { return false }',S)
  self.assertIn('old.view.removeFromSuperview()',S)
  self.assertIn('old.removeFromParent()',S)
  self.assertIn('controllers.removeValue(forKey: folder)',S)
  self.assertIn('releaseExitedController(folder: folder)',S)
  self.assertIn('viewport?.ownsController(vc, folder: vc.bundleId)',S)
  self.assertIn('canRelaunch: canRestart',S)
  self.assertIn('let activeFolders = Set(slots.map(\.id))',S)
  self.assertIn('target.contentView?.superview != nil',S)
  self.assertNotIn('.terminate()',S)
 def test_original_fullscreen_statusbar_behavior_restored(self):
  self.assertIn('assert a.count("        settings.statusBarDisabled = !self.isNativeWindow;") == 1',I)
  self.assertNotIn('settings.statusBarDisabled = !self.isNativeWindow && !self.scarletNativeFullscreenSlot;',I)
  self.assertIn('settings.safeAreaInsetsPortrait = safe',S)
  self.assertIn('fullscreen_scene_host_safe_area',S)
 def test_existing_ids_unchanged_and_pilot_opt_in(self):
  self.assertIn('experimentalFullscreenResident = false',H)
  self.assertIn('Scarlet.Feature.FullscreenResidentPilot.V45',H)
  self.assertIn('Scarlet-Crystal-V48-UNSIGNED.ipa',W)
  self.assertIn('scarlet-v48-unsigned-20261111',W)
if __name__=='__main__': unittest.main()
