"""R6P11: SDK compatibility is a general guest contract, never an app allowlist.

Device visual validation remains mandatory: dyld SDK hooks are installed after
LiveProcess NSExtensionMain has loaded UIKit, so changing SDK queries cannot
by itself prove UIKit's cached launch-time layout mode was repaired.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = (ROOT / "integration/apply_scarlet_host.py").read_text()
RECORDER = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
LEDGER = (ROOT / "HostApp/ScarletGuestSessionLedger.swift").read_text()
CUT = INTEGRATION.split("def add_r6p11_guest_sdk_contract(", 1)[1].split(
    "\ndef add_scarlet_guest_launch_policy_probe(", 1)[0]

class ResidentSDKContract(unittest.TestCase):
    def test_feature_scope_and_original_classic_paths(self):
        self.assertIn('if(defer) {', INTEGRATION)
        self.assertIn('residentInfo[@"scarletResidentSDKContract"] = @YES;', CUT)
        self.assertIn('scarletDeferExtensionRequest:NO', INTEGRATION)
        self.assertIn('retrievedAppInfo[@"scarletResidentSDKContract"]', CUT)
        self.assertIn('residentSDK = isLiveProcess && !isSideStore', CUT)
        self.assertIn('if(residentSDK && effectiveSDK == 0)', CUT)
        self.assertIn('DyldHooksInit([guestAppInfo[@"hideLiveContainer"] boolValue]', CUT)
        self.assertIn('uint32_t explicitSDK = [guestAppInfo[@"spoofSDKVersion"] unsignedIntValue];', CUT)
        self.assertIn('uint32_t effectiveSDK = explicitSDK;', CUT)
        self.assertIn('SDK already loaded by NSExtensionMain', CUT.replace(
            'UIKit was already loaded by NSExtensionMain', 'SDK already loaded by NSExtensionMain'))

    def test_read_only_real_guest_macho_build_sdk_not_bundle_flags(self):
        for text in (
            'LCParseMachO(path, true,', 'LC_BUILD_VERSION',
            'LC_VERSION_MIN_IPHONEOS', 'PLATFORM_IOS',
            'declaredMajor >= 11', 'declaredMajor <= (uint32_t)os.majorVersion',
        ):
            self.assertIn(text, CUT)
        self.assertNotIn('LCParseMachO(path, false,', CUT)
        self.assertNotIn('appBundle.infoDictionary[@"DTSDKName"]', CUT)
        self.assertNotIn('Instagram', CUT)
        self.assertNotIn('KakaoTalk', CUT)

    def test_no_existing_geometry_or_touch_rewrites(self):
        for forbidden in (
            'additionalSafeAreaInsets', 'settings.peripheryInsets',
            'settings.safeAreaEdgeInsets', 'settings.safeAreaInsetsPortrait',
            'UIWindowLevel', 'statusBarDisabled', 'setFrame:', 'setTransform:',
            'setNeedsLayout', 'scaleRatio =', 'bounds.size',
        ):
            self.assertNotIn(forbidden, CUT)
        self.assertIn('resident_sdk_contract = add_r6p11_guest_sdk_contract(engine)', INTEGRATION)
        self.assertIn('"residentGuestSDKContract": resident_sdk_contract', INTEGRATION)

    def test_anonymous_guest_receipt_is_recorded_and_exported(self):
        self.assertIn('"Scarlet.Guest.SDKContract.V1"', CUT)
        self.assertIn('ScarletRecordGuestSDKContract(effectiveSDK, sdkOrigin)', CUT)
        self.assertIn('"guest_sdk", "resident_sdk_contract_selected"', LEDGER)
        self.assertIn('replayGuestSDKContractToHostJournal()', RECORDER)
        for k in ('"sdk_major"', '"sdk_minor"', '"sdk_source"'):
            self.assertIn(k, RECORDER)
            self.assertIn(k, LEDGER)
        self.assertIn('epoch >= currentStart', LEDGER)
        self.assertIn('["guest_macho", "user_override", "no_usable_sdk"]', LEDGER)
        self.assertIn('dyld_sdk_query_requested', LEDGER)
        self.assertNotIn('bundle_id', CUT.lower())

if __name__ == "__main__":
    unittest.main()
