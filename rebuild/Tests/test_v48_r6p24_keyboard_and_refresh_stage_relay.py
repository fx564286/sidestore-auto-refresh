"""R6P24: source, generator and host dispatch/receipt regression tests.

A successful guest audio setActive receipt alone is not an acoustic measurement.
Keyboard dismissal receipt alone is not a visual keyboard-hide confirmation.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
XPC=(ROOT/'HostApp/ScarletAuthXPCSupport.swift').read_text()
NATIVE=(ROOT/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
GUIDANCE=(ROOT/'HostApp/ScarletAutomaticRenewal.swift').read_text()
GLUE=(ROOT/'integration/apply_scarlet_host.py').read_text()
KEYBOARD=(ROOT/'integration/ScarletGuestKeyboardHandoff.m.txt').read_text()
WORKFLOW=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class R6P24(unittest.TestCase):
    def test_stage_replies_not_erased_at_host_xpc_boundary(self):
        allow=XPC.split('let allowed: Set<String> = [',1)[1].split(']',1)[0]
        for code in ('native_unknown_database_stage','native_unknown_team_stage',
                     'native_unknown_transport_stage','native_unknown_appmanager_stage'):
            self.assertIn('"'+code+'"',allow)
            self.assertIn('"'+code+'"',NATIVE)
            self.assertIn('case "'+code+'"',GUIDANCE)
        self.assertIn('allowed.contains(candidateReason)',XPC)
        self.assertIn('ScarletNativeRefreshFailure(reason: status,',XPC)

    def test_outgoing_process_keyboard_closed_before_remote_view_hides(self):
        select=HOST.split('    func select(folder: String) -> Bool {',1)[1].split('    func reconcile() {',1)[0]
        self.assertLess(select.index('dismissGuestKeyboard(pid: vc.pid)'),
                        select.index('vc.view.layer.opacity ='))
        self.assertIn('key != folder',select)
        self.assertIn('audioScopedPID != target.pid',select)
        self.assertIn('postGuestAudioScope("pause", pid: vc.pid)',select)
        self.assertIn('postGuestAudioScope("resume", pid: target.pid)',select)
        home=HOST.split('    func pauseAllResidentAudioOnHome() {',1)[1].split('    func select(',1)[0]
        self.assertLess(home.index('dismissGuestKeyboard(pid: vc.pid)'),
                        home.index('postGuestAudioScope("pause", pid: vc.pid)'))

    def test_guest_focus_release_is_pid_scoped_and_resident_only(self):
        self.assertIn('com.scarlet.guest.keyboard.dismiss.%d',KEYBOARD)
        self.assertIn('com.scarlet.guest.keyboard.ack.%@.%d',KEYBOARD)
        self.assertIn('[window endEditing:YES]',KEYBOARD)
        self.assertIn('window.windowLevel == UIWindowLevelNormal',KEYBOARD)
        self.assertIn('Scarlet.ResidentSDKContract.V1',KEYBOARD)
        self.assertIn('NSUserDefaults.isLiveProcess',KEYBOARD)
        self.assertIn('UIKeyboardDidHideNotification',KEYBOARD)
        self.assertIn('ScarletGuestKeyboardAck(@"keyboard_hidden")',KEYBOARD)
        self.assertNotIn('UIApplication.sharedApplication',KEYBOARD.split('static void ScarletGuestKeyboardReleaseFocus(void) {')[1])
        self.assertNotIn('setText:',KEYBOARD)
        self.assertNotIn('kill(',KEYBOARD)
        self.assertNotIn('window.frame =',KEYBOARD)
        self.assertIn('guest_keyboard_device_receipt',HOST)
        self.assertIn('guest_keyboard_dismiss_requested',HOST)

    def test_generator_wires_real_extension_tweak_once(self):
        spec=importlib.util.spec_from_file_location('scarlet_host_glue',ROOT/'integration/apply_scarlet_host.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with TemporaryDirectory() as td:
            eng=Path(td)
            tweaks=eng/'LiveContainer/Tweaks'
            tweaks.mkdir(parents=True)
            (tweaks/'Tweaks.h').write_text('void initScarletGuestIslandContentGuard(void);\n')
            (eng/'LiveContainer/LCBootstrap.m').write_text('        initScarletGuestIslandContentGuard();\n')
            report=module.add_scarlet_guest_keyboard_handoff(eng)
            self.assertTrue(report['residentOnly'])
            self.assertTrue(report['firstResponderRelease'])
            self.assertTrue((tweaks/'ScarletGuestKeyboardHandoff.m').is_file())
            self.assertEqual((tweaks/'Tweaks.h').read_text().count('void initScarletGuestKeyboardHandoff(void);'),1)
            self.assertEqual((eng/'LiveContainer/LCBootstrap.m').read_text().count('        initScarletGuestKeyboardHandoff();'),1)
        self.assertIn('keyboard_handoff = add_scarlet_guest_keyboard_handoff(engine)',GLUE)
        self.assertIn('"guestKeyboardHandoff": keyboard_handoff',GLUE)

    def test_no_audio_route_or_layout_regression_or_new_bundle_id(self):
        self.assertIn('ScarletGuestAudioReceipt(NO, result)',GLUE)
        self.assertIn('if(!result && attempt < 2)',GLUE)
        self.assertIn('"guest_audio_device_receipt"',HOST)
        self.assertNotIn('AVAudioSession.sharedInstance.setCategory',HOST)
        self.assertNotIn('vc.scaleRatio = 0.',HOST)
        self.assertIn('vc.scaleRatio = 1',HOST)
        self.assertNotIn('PRODUCT_BUNDLE_IDENTIFIER',KEYBOARD)
        self.assertIn('fix/scarlet-v48-r6p24-keyboard-stage-relay-20261112',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6P24-KEYBOARD-STAGE-UNSIGNED.ipa',WORKFLOW)

if __name__=='__main__':
    unittest.main()
