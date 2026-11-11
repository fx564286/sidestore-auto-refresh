"""V11 architectural guards: real built-in modules, no extra App ID targets."""
from pathlib import Path
import importlib.util
import plistlib
import tempfile
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
MODULE=(ROOT/"HostApp/ScarletFeatureModulesSection.swift").read_text()
GUEST=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
SCRIPT=ROOT/"scripts/audit_appid_footprint.py"
SPEC=importlib.util.spec_from_file_location("appid_footprint",SCRIPT)
AUDIT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
BASE=AUDIT.HOST_ID


def fixture(path, *, include_launch=True, extra=False):
    def encode(x): return plistlib.dumps(x)
    with ZipFile(path,"w") as z:
        z.writestr("Payload/LiveContainer.app/Info.plist",
                   encode({"CFBundleIdentifier":BASE}))
        for name,ext_id in AUDIT.REQUIRED_EXTENSIONS.items():
            if name=="LaunchAppExtension" and not include_launch: continue
            typ=("com.apple.appintents-extension" if name=="LaunchAppExtension"
                 else ("com.apple.share-services" if name == "ShareExtension"
                       else "com.apple.extensionkit-service"))
            info={"CFBundleIdentifier":ext_id,
                  "NSExtension":{"NSExtensionPointIdentifier":typ}}
            if name=="LaunchAppExtension":
                info["EXAppExtensionAttributes"]={"EXExtensionPointIdentifier":typ}
            z.writestr("Payload/LiveContainer.app/PlugIns/"+name+".appex/Info.plist",
                       encode(info))
        if extra:
            z.writestr("Payload/LiveContainer.app/PlugIns/Unexpected.appex/Info.plist",
                       encode({"CFBundleIdentifier":BASE+".Unexpected",
                               "NSExtension":{"NSExtensionPointIdentifier":"com.apple.share-services"}}))


class ScarletModularArchitecture(unittest.TestCase):
    def test_module_control_is_real_and_persisted(self):
        for fragment in ('@AppStorage("Scarlet.Feature.SwitcherMotion.V1"',
                         '@AppStorage("Scarlet.Feature.SwitcherHaptics.V1"',
                         'store: LCUtils.appGroupUserDefault',
                         'Toggle("멀티탭 전환 애니메이션"',
                         'Toggle("멀티탭 진동 피드백"',
                         'containerURL(',):
            self.assertIn(fragment,MODULE)
        for fragment in ('withAnimation(morphAnimation)',
                         '.animation(morphAnimation, value: isOpen)',
                         'if switcherHaptics {',
                         'buttonCenter.x',
                         'buttonCenter.y'):
            self.assertIn(fragment,GUEST)
        self.assertNotIn('let cx = overlay.dockRight ?',GUEST)
        self.assertNotIn("dlopen(",MODULE)

    def test_module_settings_inside_original_lc_form(self):
        self.assertIn('ScarletFeatureModulesSection()',PATCH)
        self.assertIn('ScarletFeatureModulesSection.swift',PATCH)
        self.assertIn('ScarletSigningReadinessPanel()',PATCH)
        self.assertIn('Preserve upstream localized certificate alerts verbatim',PATCH)
        self.assertNotIn("shutil.rmtree(",PATCH)

    def test_ipa_four_bundle_ids_and_different_extension_points(self):
        with tempfile.TemporaryDirectory() as d:
            ipa=Path(d)/"test.ipa"
            fixture(ipa)
            report=AUDIT.inspect_ipa(ipa)
            self.assertEqual(report["total_bundle_ids"],4)
            self.assertEqual(report["extension_app_ids"],3)
            self.assertFalse(report["built_in_feature_modules_add_app_ids"])
            self.assertFalse(report["free_team_provisioning_verified"])
            self.assertFalse(report["safe_to_merge_extensions_automatically"])
            ext={item["name"]:item["extension_point"] for item in report["extensions"]}
            self.assertEqual(ext["LaunchAppExtension"],"com.apple.appintents-extension")
            self.assertEqual(ext["ShareExtension"],"com.apple.share-services")

    def test_unknown_missing_or_duplicate_extension_blocks_packaging(self):
        with tempfile.TemporaryDirectory() as d:
            ipa=Path(d)/"test.ipa"
            fixture(ipa, include_launch=False)
            with self.assertRaisesRegex(ValueError,"Extension set changed"):
                AUDIT.inspect_ipa(ipa)
            fixture(ipa, extra=True)
            with self.assertRaisesRegex(ValueError,"Extension set changed"):
                AUDIT.inspect_ipa(ipa)

if __name__ == "__main__": unittest.main()
