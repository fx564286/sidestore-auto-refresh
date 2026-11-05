"""Regression: keep installed build metadata distinct from signed remote releases."""
from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[1]
SWIFT=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text()
OTA=SWIFT.split("// SCARLET_V189_SIGNED_RELEASE_IDENTITY:",1)[1]

class ScarletOTAIdentityTests(unittest.TestCase):
    def test_no_stale_nrg_release_channel(self):
        self.assertNotIn("releases/latest",OTA)
        self.assertNotIn('tag.hasPrefix("nrg-ota-v")',OTA)
        self.assertIn("device-signed",OTA)
        self.assertIn("SIGNED-DEVELOPMENT.ipa",OTA)
        self.assertIn("Scarlet-V\\(number)-SIGNED.sha256",OTA)

    def test_installed_release_is_not_default_zero(self):
        self.assertIn('object(forInfoDictionaryKey: "ScarletBuildLabel")',OTA)
        self.assertNotIn('object(forInfoDictionaryKey: "NRGOTASequence")',OTA)
        self.assertIn("private var current: Int?",OTA)
        self.assertIn("return nil",OTA)
        self.assertIn('object(forInfoDictionaryKey: "CFBundleVersion")',OTA)

    def test_swift_interpolation_is_not_escaped_as_literal(self):
        self.assertNotIn('Text("#\\\\(current)")',OTA)
        self.assertNotIn('Label("빌드 #\\\\(build.version)',OTA)
        self.assertIn('V\\(build.version) 검증 후 SideStore로 전달',OTA)
        self.assertIn('Text("IPA 빌드: \\(bundleBuild)")',OTA)

    def test_download_is_not_claimed_to_be_installed(self):
        self.assertIn("install_result=unverified",OTA)
        self.assertIn("SHA256()",OTA)
        self.assertIn("status.stageSharedIPA",OTA)
        self.assertIn("다운로드·서명 요청은 설치 성공이 아니야",OTA)

    def test_unique_build_label(self):
        p=ROOT/"scripts/v189_package_fork.py"
        source=p.read_text()
        ast.parse(source)
        self.assertIn('EXPECTED_VERSION = "V189"',source)
        self.assertIn('data["CFBundleVersion"] = "3.8.203"',source)
        self.assertIn('data["ScarletUpdateChannel"] = "scarlet-device-signed"',source)
        self.assertIn('if data.get("CFBundleVersion") != "3.8.202":',source)
        self.assertIn('value["ScarletBuildLabel"] = EXPECTED_VERSION',
                      (ROOT/"scripts/v181_package_fork.py").read_text())

    def test_glass_and_existing_route_unchanged(self):
        self.assertIn("V3_UNIFIED_SHELL_V1_END",SWIFT)
        self.assertIn("V3SideStoreStatusStore",SWIFT)
        self.assertIn("V3AuthStore",SWIFT)

if __name__=="__main__":
    unittest.main()
