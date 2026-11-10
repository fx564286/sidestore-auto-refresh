"""Safety regression: iPhone guest must use unscaled original LC screen."""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
GUEST=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
LEDGER=(R/'HostApp/ScarletGuestSessionLedger.swift').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class FullscreenSafety(unittest.TestCase):
    def test_iphone_never_uses_virtual_window(self):
        self.assertIn('if UIDevice.current.userInterfaceIdiom == .phone {',HOST)
        self.assertIn('try await app.runApp(multitask: false)',HOST)
        self.assertIn('original_fullscreen_policy',HOST)
        self.assertIn('"virtual_window": "disabled"',HOST)
        self.assertIn('"guest_geometry": "original"',HOST)
        for key in ('LCLaunchInMultitaskMode', 'LCLaunchMultitaskMaximized',
                    'LCMaxOneAppOnStage'):
            self.assertIn('set(false, forKey: "'+key+'")',HOST)
        for bad in ('useVirtual','MultitaskMode.virtualWindow',
                    'virtual_guest_resident','virtual_guest_unverified'):
            self.assertNotIn(bad,HOST)

    def test_existing_native_scene_path_is_ipad_only(self):
        start=HOST.index('if #available(iOS 16.1, *),',
                         HOST.index('ScarletGuestSessionLedger.noteLaunch('))
        end=HOST.index('try await app.runApp(multitask: true)',start)
        segment=HOST[start:end]
        self.assertIn('UIDevice.current.userInterfaceIdiom == .pad',segment)
        self.assertIn('UIApplication.shared.supportsMultipleScenes',segment)
        self.assertIn('MultitaskMode.nativeWindow.rawValue',segment)

    def test_guest_switcher_has_no_v34_host_bridge(self):
        for source in (HOST,GUEST,LEDGER):
            self.assertNotIn('ScarletGuestLiveBridge',source)
        self.assertNotIn('Scarlet.Guest.LiveContainers.V34',LEDGER)
        self.assertIn('LCSharedUtils.launchToGuestApp(',GUEST)
        self.assertIn('"memory": "not_preserved"',GUEST)
        for bad in ('appSceneVC.view.frame =','root.view.frame =',
                    'appData["UISupportedInterfaceOrientations"] = ',
                    'orientationLock =','UIInterfaceOrientationMaskLandscape'):
            self.assertNotIn(bad,GUEST)

    def test_v35_ci_release_branch(self):
        self.assertIn('fix/scarlet-v35-restore-original-fullscreen-20261110',
                      WORKFLOW)
        self.assertIn('Scarlet-Crystal-V35-UNSIGNED.ipa',WORKFLOW)

if __name__=='__main__':
    unittest.main()
