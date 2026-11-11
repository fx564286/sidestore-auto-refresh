"""R6P7 boot-policy differential: not a Safe Area or UIKit workaround.

Source-level validation only. A device observation is required to determine
whether app-level metadata contributes to the Dynamic Island overlap.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
I = (ROOT / "integration/apply_scarlet_host.py").read_text()
L = (ROOT / "HostApp/ScarletGuestSessionLedger.swift").read_text()
D = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
S = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()

class BootstrapLaunchPolicy(unittest.TestCase):
    def test_original_lc_bootloader_owns_the_probe(self):
        self.assertIn('target = engine / "LiveContainer/LCBootstrap.m"', I)
        self.assertIn('ScarletGuestLaunchPolicySnapshot(@"before_bundle_swap", appBundle);', I)
        self.assertIn('ScarletGuestLaunchPolicySnapshot(@"after_bundle_swap", appBundle);', I)
        self.assertIn('overwriteMainNSBundle(appBundle);', I)
        self.assertIn('overwriteMainCFBundle();', I)

    def test_compares_host_guest_and_effective_main_bundle(self):
        for x in ('lcMainBundle.infoDictionary', 'guestBundle.infoDictionary',
                  'NSBundle.mainBundle.infoDictionary', 'CFBundleGetMainBundle()',
                  'UIStatusBarHidden', 'UIViewControllerBasedStatusBarAppearance',
                  'UIApplicationSceneManifest', 'UIRequiresFullScreen',
                  'UISupportedInterfaceOrientations'):
            self.assertIn(x, I)

    def test_no_unsafe_mutation_of_guest_launch_policy(self):
        probe = I.split('def add_scarlet_guest_launch_policy_probe(', 1)[1].split(
            '\ndef add_scarlet_guest_audio_isolation(', 1)[0]
        for forbidden in ('setAdditionalSafeAreaInsets', 'safeAreaEdgeInsets',
                          'statusBarDisabled =', 'setFrame(', 'UIWindow *window =',
                          'swizzle(', 'UIStatusBarHidden] =', 'UIRequiresFullScreen] ='):
            self.assertNotIn(forbidden, probe)
        self.assertIn('if(!isLiveProcess || !guestBundle || !lcSharedDefaults) return;', probe)

    def test_bounded_anonymous_relay_to_existing_diagnostics(self):
        self.assertIn('Scarlet.Guest.LaunchPolicy.V1', I)
        self.assertIn('Scarlet.Guest.LaunchPolicy.V1', L)
        self.assertIn('guest_bundle_policy_observed', L)
        self.assertIn('epoch >= currentStart', L)
        self.assertIn('n >= -1 && n <= 20', L)
        self.assertIn('replayGuestLaunchPolicyToHostJournal()', D)
        self.assertIn('if(items.count > 16)', I)

    def test_preserves_successful_r6p4_multitasking_and_audio(self):
        self.assertIn('home_audio_reactivation_suppressed', S)
        self.assertIn('guest_audio_device_receipt', S)
        self.assertIn('fullscreen_scene_direct_switch', S)

if __name__ == '__main__':
    unittest.main()
