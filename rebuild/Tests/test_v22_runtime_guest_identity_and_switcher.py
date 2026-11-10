"""V22 regression for V21 iPhone diagnostic: active A/B misclassified cold.

User's V21 iPhone log SourceCommit 79619ca56f96: panel_opened(count=2),
switch_tapped_cold, switch_submitted, with no proof both apps are resident.
LC's bootstrap consumes/removes selected and NSUserDefaults.standard is
virtualized to the guest. The TweakLoader's lcGuestAppId is runtime identity.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOOK=(ROOT/"integration/apply_scarlet_host.py").read_text()
FULL=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
LEDGER=(ROOT/"HostApp/ScarletGuestSessionLedger.swift").read_text()
NATIVE=(ROOT/"HostApp/ScarletGuestSwitcherOverlay.swift").read_text()

class V22RuntimeGuestIdentity(unittest.TestCase):
    def test_guest_hook_passes_real_livecontainer_bundle_id(self):
        self.assertIn('NSString *guestID = NSUserDefaults.lcGuestAppId;', HOOK)
        self.assertIn('objc_msgSend)(provider,callback,guestID);', HOOK)
        self.assertNotIn('objc_msgSend)(provider,callback,title);', HOOK)
        self.assertIn('SEL callback = NSSelectorFromString(@\\\"installForGuestName:\\")',HOOK)
        self.assertIn('ScarletGuestHookTrace(@\\\"hook_entered\\\")',HOOK)

    def test_current_guest_has_one_authoritative_identity(self):
        self.assertIn('let runtimeGuestID = rawName as String',FULL)
        self.assertIn('reloadApps: { installedApps(guestIdentifier: runtimeGuestID) }',FULL)
        self.assertIn('onSwitch: { switchGuest(to: $0, runtimeGuestID: runtimeGuestID) }',FULL)
        self.assertIn('let runtimeID = guestIdentifier?.trimmingCharacters', FULL)
        self.assertIn('let hasRuntimeIdentity = runtimeID.map { !$0.isEmpty } ?? false',FULL)
        self.assertIn('let isCurrent = hasRuntimeIdentity && matchesRuntime',FULL)
        self.assertIn('let isCurrent = hasRuntimeIdentity && matchesRuntime',FULL)
        self.assertNotIn(': (folder == selected || bundleID == selected)',FULL)
        self.assertIn('let originalBundleID = meta["LCOrignalBundleIdentifier"] as? String',FULL)
        self.assertNotIn('folder == guestIdentifier || bundleID == guestIdentifier',FULL)
        self.assertNotIn('UserDefaults.standard.string(forKey: "selected")',FULL)

    def test_current_guest_cannot_self_cold_relaunch(self):
        self.assertIn('guard !target.isCurrent, target.id.hasSuffix(".app")',FULL)
        self.assertIn('let latest = installedApps(guestIdentifier: runtimeGuestID).first(where:',FULL)
        self.assertIn('$0.id == target.id && !$0.isCurrent',FULL)
        self.assertIn('if target.isCurrent {',FULL)
        self.assertIn('closePanel()',FULL)
        self.assertIn('apps.filter { !$0.isCurrent }',FULL)

    def test_trace_runtime_classification_without_app_name(self):
        self.assertIn('runtime_current_resolved',FULL)
        self.assertIn('runtime_current_unresolved',FULL)
        self.assertIn('runtime_identity_classified', FULL)
        self.assertIn('"count": String(currentCount)',FULL)
        self.assertIn('ScarletGuestSessionLedger.traceSwitcher(',FULL)
        self.assertIn('Scarlet.Guest.ActiveSwitcherSession.V19',LEDGER)
        self.assertNotIn('removePersistentDomain(',FULL)

    def test_visual_and_data_invariants(self):
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',FULL)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)',FULL)
        self.assertIn('SCARLET_GUEST_CURRENT_RUNNING',FULL)
        self.assertIn('@State private var isOpen = false',FULL)
        self.assertIn('@State private var isOpen = false',NATIVE)
        self.assertIn('let recent = ScarletGuestSessionLedger.recent()',FULL)
        self.assertIn('private static let maxItems = 8',LEDGER)

    def test_runtime_identity_reference_model(self):
        # Emulate authoritative LC original bundle identity and single guest:
        installed=[("Instagram.app","com.burbn.instagram",None),
                   ("KakaoTalk.app","com.iwilab.KakaoTalk",None)]
        runtime="com.iwilab.KakaoTalk"
        detected=[folder for folder,bundle,orig in installed
                  if bundle==runtime or orig==runtime]
        self.assertEqual(detected,["KakaoTalk.app"])
        other=[folder for folder,bundle,orig in installed if folder not in detected]
        self.assertEqual(other,["Instagram.app"])
        # Stale selected is ignored whenever runtime identity exists.
        stale_selected="Instagram.app"
        self.assertNotIn(stale_selected,detected)

if __name__=="__main__":
    unittest.main()
