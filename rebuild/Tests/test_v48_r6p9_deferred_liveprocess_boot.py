"""R6P9: prevent resident guest app bootstrap before host-window ownership.

This tests the native source generation and original launch contract.
CI native Xcode archives must additionally prove Objective-C/Swift bridging;
only on-device verification can prove Dynamic Island visual correctness.
"""
from pathlib import Path
import re
import unittest

R = Path(__file__).resolve().parents[1]
I = (R/"integration/apply_scarlet_host.py").read_text()
S = (R/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
D = (R/"HostApp/ScarletDiagnosticRecorder.swift").read_text()

class ResidentHostWindowFirst(unittest.TestCase):
    def test_deferred_initializer_preserves_original_immediate_path(self):
        glue = I.split("def add_r6p9_deferred_liveprocess_boot(", 1)[1].split(
            "\ndef add_scarlet_guest_launch_policy_probe(", 1)[0]
        self.assertIn('scarletDeferExtensionRequest:NO', glue)
        self.assertIn('scarletDeferExtensionRequest:(BOOL)defer', glue)
        self.assertIn('self.scarletPendingExtensionItem = item;', glue)
        self.assertIn('if(defer)', glue)
        self.assertIn('self.scarletPendingExtensionItem = nil;', glue)
        self.assertIn('beginExtensionRequestWithInputItems:@[item]', glue)
        self.assertIn('return [self initWithBundleId:bundleId dataUUID:dataUUID', glue)
        self.assertIn('extensionStartSites": 1', glue)
        self.assertIn('classicLaunchImmediate": True', glue)

    def test_boot_request_requires_actual_window_scene_and_parent(self):
        glue = I.split("def add_r6p9_deferred_liveprocess_boot(", 1)[1].split(
            "\ndef add_scarlet_guest_launch_policy_probe(", 1)[0]
        for required in (
            'self.scarletPendingExtensionItem',
            '!self.scarletNativeFullscreenSlot',
            '!self.isViewLoaded',
            '!self.view.window',
            '!self.view.window.windowScene',
            '!self.parentViewController',
        ):
            self.assertIn(required, glue)
        self.assertIn('if vc.scarletBeginDeferredExtensionIfHosted() {', S)
        self.assertIn('controllers[slot.id] = vc', S)
        self.assertLess(S.index('controllers[slot.id] = vc'),
                        S.index('if vc.scarletBeginDeferredExtensionIfHosted() {'))
        self.assertIn('scarletDeferExtensionRequest: true', S)
        self.assertIn('fullscreen_scene_xpc_started_after_host_attach', S)

    def test_does_not_change_geometry_safarea_or_guest_lifecycle(self):
        glue = I.split("def add_r6p9_deferred_liveprocess_boot(", 1)[1].split(
            "\ndef add_scarlet_guest_launch_policy_probe(", 1)[0]
        for forbidden in (
            'settings.safeAreaEdgeInsets =', 'additionalSafeAreaInsets =',
            'settings.statusBarDisabled =', 'settings.peripheryInsets =',
            'settings.frame =', 'setFrame:', 'UIApplicationSceneManifest] =',
            'UIStatusBarHidden] =', 'setTransform:',
        ):
            self.assertNotIn(forbidden, glue)
        self.assertIn('vc.scaleRatio = 1', S)
        self.assertIn('settings.setFrame(full)', S)
        self.assertIn('home_audio_reactivation_suppressed', S)
        self.assertIn('guest_audio_device_receipt', S)
        self.assertIn('fullscreen_scene_direct_switch', S)

    def test_integration_receipt_and_existing_log_allowlist(self):
        self.assertIn('deferred_scene_boot = add_r6p9_deferred_liveprocess_boot(engine)', I)
        self.assertIn('deferredRemoteLaunchUntilHosted', I)
        self.assertIn('"guest", "fullscreen_scene_xpc_started_after_host_attach"', S)
        for field in ('"result"', '"stage"'):
            self.assertIn(field, D)
        self.assertIn('guestLaunchPolicyDifferential', I)

if __name__ == "__main__":
    unittest.main()
