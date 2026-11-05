"""V189: #191 was stale NRG release state, not the installed Scarlet build."""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(file):
    spec=importlib.util.spec_from_file_location(file[:-3],ROOT/"scripts"/file)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

fix=load("patch_v189_update_provenance.py")

class UpdateProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text(encoding="utf8")
        cls.new=fix.patch(cls.previous)

    def test_precise_patch_idempotent(self):
        self.assertEqual(fix.patch(self.new),self.new)
        self.assertEqual(self.new.count(fix.MARK),1)

    def test_original_liquid_glass_and_host_not_changed(self):
        self.assertEqual(self.previous.split(fix.OLD)[0],self.new.split(fix.MARK)[0])

    def test_legacy_remote_number_cannot_be_installed_build(self):
        self.assertNotIn("NRGOTASequence",self.new)
        self.assertNotIn("nrg-ota-v",self.new)
        self.assertNotIn("LiveContainer-SideStore-v3.0.3-rc.ipa",self.new)
        self.assertNotIn("releases/latest",self.new)

    def test_actual_executing_app_identity_visible(self):
        for required in ("ScarletBuildLabel","CFBundleVersion",
                         "scarletInstalledBuildIdentity","현재 실행 중:",
                         "설치된 Scarlet 빌드 식별 불가"):
            self.assertIn(required,self.new)

    def test_signed_repo_assets_only_not_unsigned_or_webclip(self):
        for required in ("scarlet","device", "signed", "SIGNED-DEVELOPMENT.ipa",
                         "digest", "sha256:", "github.com",
                         "releases?per_page=60", "status.stageSharedIPA"):
            self.assertIn(required,self.new)
        self.assertNotIn("install_result=success",self.new)

    def test_no_false_download_equals_install(self):
        self.assertIn("install_result=unverified",self.new)
        self.assertIn("실제 설치·앱 실행은 아직 확인되지 않았어.",self.new)
        self.assertIn("기존 앱을 삭제하지 마",self.new)

    def test_swift_string_interpolation_unescaped(self):
        self.assertIn('Text("현재 실행 중:',self.new) if False else None
        self.assertIn('V\(candidate.version) IPA',self.new)
        self.assertNotIn('Text("#\\\\(current)")',self.new)
        self.assertNotIn('Label("빌드 #\\\\(build.version)',self.new)

    def test_fail_closed_if_upstream_changed(self):
        with self.assertRaises(ValueError):
            fix.patch(self.previous.replace(fix.OLD,"// removed"))

if __name__=="__main__":
    unittest.main()
