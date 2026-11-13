"""P47 signed-P46 regression: foreground retry, real native status-bar ownership.

Static contracts and native Xcode success are NOT proof of visible status icons
or continuous unclipped scrolling on a signed iPhone.
"""
from pathlib import Path
import hashlib
import unittest
P=Path(__file__).resolve().parents[1]
H=(P/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
G=(P/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
UI=(P/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
SW=(P/'HostApp/ScarletIntegratedHostView.swift').read_text()
WF=(P.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
REC=(P/'HostApp/ScarletDiagnosticRecorder.swift').read_text()

class P47LifecycleHeaderProof(unittest.TestCase):
    def test_one_shot_initial_and_existing_foreground_sample(self):
        body=G.split('static void ScarletIslandTryP44LocalHeaderTransform(\n',2)[-1]
        body=body.split('static void ScarletIslandTryDeepHeaderSafeGuideAnchor(',1)[0]
        self.assertIn('(sample!=650 && sample!=2600)',body)
        self.assertIn('objc_getAssociatedObject(root,&scarletIslandP44HeaderTransformTrialKey)',body)
        self.assertIn('window.windowScene.activationState!=UISceneActivationStateForegroundActive',body)
        self.assertIn('if(sample==2600) {',body)
        self.assertIn('guest_header_postforeground_trial_staged',body)
        self.assertNotIn('window.frame=',body)
        self.assertNotIn('root.transform=',body)
        self.assertIn('header.transform=CGAffineTransformTranslate(original,0,safeTop)',body)

    def test_late_sample_keeps_native_956_scene_until_readback(self):
        body=H.split('private func onUnsafeGuestControls(',1)[-1].split('private func onNativeHeaderTransform(',1)[0]
        self.assertIn('!self.chromeLateTrialPIDs.contains(pid)',body)
        self.assertIn('chromeLateTrialPIDs.insert(pid)',body)
        self.assertIn('deadline: .now() + 1.7',body)
        self.assertIn('guest_header_foreground_retry_window',body)
        self.assertIn('chromePendingFallbackPIDs.remove(pid)',body)
        self.assertIn('applyP43FallbackChrome(pid:',body)
        self.assertIn('chromeLateTrialPIDs.remove(pid)',H)
        self.assertIn('chromeLateTrialPIDs.remove(old.pid)',H)
        self.assertIn('settings.setFrame(rect)',H) # safe fail-closed P43 unchanged
        self.assertIn('let top = reserved ? chromeTop(in: scene) : 0',H)

    def test_nonkey_resident_window_below_native_statusbar(self):
        a=UI.split('static func makeResidentSwitcherWindow(',1)[1].split('return overlay',1)[0]
        self.assertIn('overlay.windowLevel = UIWindow.Level.normal + 1',a)
        self.assertIn('let root = ScarletResidentStatusBarHostingController(rootView: content)',a)
        self.assertIn('overlay.residentHostOwnsOutsideTaps = true',a)
        self.assertIn('overlay.isHidden = false',a)
        self.assertNotIn('overlay.makeKeyAndVisible()',a)
        # Classic bootstrap path retains exact old UI layering.
        prior=UI.split('static func makeResidentSwitcherWindow(',1)[0]
        self.assertIn('overlay.windowLevel = UIWindow.Level.alert + 1',prior)

    def test_real_native_statusbar_visibility_and_contrast(self):
        cls=UI.split('final class ScarletResidentStatusBarHostingController<Content: View>',1)[1]
        self.assertIn('override var prefersStatusBarHidden: Bool { false }',cls)
        self.assertIn('override var preferredStatusBarStyle: UIStatusBarStyle { residentBarStyle }',cls)
        self.assertIn('override var childForStatusBarHidden: UIViewController? { nil }',cls)
        self.assertIn('scene.statusBarManager?.isStatusBarHidden',UI)
        self.assertIn('scene.statusBarManager?.statusBarStyle.rawValue',UI)
        self.assertIn('chromeStatusBarPreference = isLight ? .darkContent : .lightContent',H)
        self.assertIn('ScarletFullscreenGuestTabInstaller.updateResidentStatusBar(',H)
        self.assertIn('override var prefersStatusBarHidden: Bool { false }',H)
        self.assertIn('.statusBarHidden(false)',SW)
        self.assertNotIn('UILabel(text: "battery',cls)
        self.assertNotIn('UIDevice.current.batteryLevel',cls)
        for key in ('status_hidden','status_style_raw','preferred_style_raw','overlay_window_level','overlay_is_key'):
            self.assertIn('"'+key+'"',REC)
        self.assertIn('resident_native_status_bar_readback',UI)

    def test_v48_gesture_original_pan_bytes_still_exact(self):
        c=UI[UI.index('// UIkit pan tracks finger'):UI.index('@objc(ScarletFullscreenGuestTabInstaller)')]
        p=UI[UI.index('    private static func panChanged('):UI.index('    private static func resizeOverlay(')]
        self.assertEqual(hashlib.sha256(c.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
        self.assertEqual(hashlib.sha256(p.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
        self.assertNotIn('bundleID == "com.burbn.instagram"',H)

    def test_release_is_separate_and_unsigned(self):
        self.assertIn('fix/scarlet-v48-r6p47-lifecycle-statusbar-20261113',WF)
        self.assertIn('scarlet-v48-r6p47-lifecycle-statusbar-unsigned-20261113',WF)
        self.assertIn('Scarlet-Crystal-V48-R6P47-LIFECYCLE-STATUSBAR-UNSIGNED.ipa',WF)
        self.assertIn('scarlet-v48-r6p46-detached-full-scroll-unsigned-20261113',WF)

if __name__=='__main__':unittest.main()
