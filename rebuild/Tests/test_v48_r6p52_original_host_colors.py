"""P52: user-unauthorized root ColorScheme override removed, no guest frame changes."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
STACK=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GLASS=(ROOT/'HostApp/ScarletNativeGlass.swift').read_text()
WF=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
PATCH=(ROOT/'integration/apply_scarlet_host.py').read_text()
class P52OriginalHostColors(unittest.TestCase):
 def test_no_global_palette_override_or_swiftui_override_trait(self):
  self.assertNotIn('.preferredColorScheme(',HOST)
  self.assertNotIn('.environment(\\.colorScheme',HOST)
  self.assertNotIn('.overrideUserInterfaceStyle',HOST)
  self.assertIn('.scarletSettingsPurplePalette()',PATCH)
  self.assertIn('func scarletSettingsPurplePalette() -> some View',GLASS)
  self.assertIn('UIGlassEffect(style: .clear)',GLASS)
 def test_guest_status_tone_is_passive_and_logs_do_not_claim_success(self):
  self.assertIn('resident_key_host_status_bar_tone_observed',STACK)
  self.assertIn('guest_tone_read_only_original_palette_preserved',STACK)
  self.assertIn('unforced_host_status_style_mismatch_guest',STACK)
  self.assertNotIn('key_scene_color_scheme_published',STACK)
  self.assertIn('scene.statusBarManager?.statusBarStyle.rawValue',STACK)
 def test_p51_status_collision_and_p50_crop_remain_independent(self):
  self.assertIn('.statusBarHidden(fullscreenStack.isVisible &&',HOST)
  self.assertIn('fullscreenStack.nativeStatusBarCollisionShield',HOST)
  self.assertIn('nativeStatusBarCollisionShield = true',STACK)
  self.assertIn('nativeStatusBarUnsafePIDs.insert(pid)',STACK)
  self.assertIn('chromeScrollCropVetoPIDs.contains(pid)',STACK)
  self.assertIn('let rect = contentSlot(in: scene, reserved: reserved)',STACK)
 def test_separate_p52_ipa_release(self):
  self.assertIn('fix/scarlet-v48-r6p51-native-statusbar-collision-shield-20261113',WF)
  self.assertIn('fix/scarlet-v48-r6p52-restore-original-host-colors-20261113',WF)
  self.assertIn('scarlet-v48-r6p52-original-colors-unsigned-20261113',WF)
  self.assertIn('Scarlet-Crystal-V48-R6P52-ORIGINAL-COLORS-UNSIGNED.ipa',WF)
if __name__=='__main__':unittest.main()
