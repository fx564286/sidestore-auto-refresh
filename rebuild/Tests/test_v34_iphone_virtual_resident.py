"""V34: iPhone original LiveProcess virtual-window continuity.
Real memory retention is subject to iOS process lifetime and user device QA.
"""
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
G=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
L=(R/'HostApp/ScarletGuestSessionLedger.swift').read_text()
CI=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class V34IPhoneResident(unittest.TestCase):
    def test_ios_iphone_virtual_not_gated_on_native_scenes(self):
        start=H.index('let virtualOnPhone = UIDevice.current.userInterfaceIdiom == .phone')
        end=H.index('                // runApp returning is NOT proof',start)
        source=H[start:end]
        self.assertIn('LCUtils.liveProcessBundleIdentifier() != nil', source)
        self.assertIn('(virtualOnPhone || nativeScenesAvailable)',source)
        self.assertIn('useVirtual ? .virtualWindow : .nativeWindow', source)
        self.assertIn('prefs.set(mode.rawValue, forKey: "LCMultitaskMode")',source)
        self.assertIn('try await app.runApp(multitask: true)',source)
        self.assertIn('try await app.runApp()',source)
        self.assertNotIn('guard UIApplication.shared.supportsMultipleScenes',source)
        self.assertIn('"LCLaunchMultitaskMaximized"', source)
        self.assertIn('"LCMaxOneAppOnStage"',source)
        self.assertIn('ScarletGuestSessionLedger.restore(historyBeforeLaunch)',source)

    def test_host_posts_live_slot_only_for_real_original_lc_session(self):
        self.assertIn('MultitaskManager.isUsing(container: $0)',H)
        self.assertIn('if resident, let container {',H)
        self.assertIn('ScarletGuestLiveBridge.noteLiveContainer(container)',H)
        self.assertIn('virtual_guest_resident',H)
        self.assertIn('virtual_guest_unverified',H)
        self.assertIn('ScarletGuestLiveBridge.installHostReceiver()',H)

    def test_cross_process_guest_switch_is_not_false_local_static_assumption(self):
        self.assertIn('ScarletGuestLiveBridge.isHostKnownLive($0)',G)
        self.assertIn('ScarletGuestLiveBridge.requestHostLiveSwitch(container)',G)
        self.assertIn('switch_host_live_requested',G)
        self.assertIn('MultitaskDockManager.shared.bringMultitaskViewToFront(',L)
        self.assertIn('let resident = MultitaskManager.isUsing(container:',L)
        self.assertIn('live_window_resumed',L)
        self.assertIn('live_window_unavailable',L)
        self.assertIn('eventName as CFString',L)
        self.assertIn('CFNotificationCenterGetDarwinNotifyCenter()',L)
        self.assertIn('defaults.synchronize()',L)

    def test_payload_is_anonymous_and_stale_live_markers_pruned(self):
        self.assertIn('Scarlet.Guest.LiveContainers.V34',L)
        self.assertIn('Scarlet.Guest.LiveSwitchRequest.V34',L)
        self.assertIn('known.filter { $0 != request.container }',L)
        self.assertIn('request.nonce != lastHandledNonce',L)
        self.assertIn('age < 10',L)
        self.assertNotIn('screenshot',L[L.index('// V34: LiveContainer'):])
        self.assertNotIn('removePersistentDomain(',L)
        self.assertIn('return true  // request delivered; NOT a verified window switch',L)

    def test_preserve_original_fullscreen_and_input_layout_constraints(self):
        for bad in ('appSceneVC.view.frame =', 'UIInterfaceOrientationMaskLandscape',
                    'original.frame =', 'appData["UISupportedInterfaceOrientations"] = '):
            self.assertNotIn(bad,G)
        self.assertIn('LCSharedUtils.launchToGuestApp(',G)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius:',G)
        self.assertIn('fix/scarlet-v34-iphone-virtual-resident-20261110',CI)

if __name__=='__main__': unittest.main()
