"""P60: SideInstaller always appends team ID; prepare source IPA for the EXISTING installed host."""
import importlib.util
import plistlib
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/"integration/prepare_sideinstaller_ipa.py"
WF=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
spec=importlib.util.spec_from_file_location("scarlet_p60_sideinstaller",MODULE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
TEAM="P8EZT3U5N4"
EXPECTED="com.kdt.livecontainer."+TEAM
BASE="com.kdt.livecontainer"
APP="Payload/LiveContainer.app/"

def make_ipa(path,wrong_id=False):
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for ext in (None,*mod.EXTENSIONS):
            name=APP+("PlugIns/"+ext+".appex/" if ext else "")+"Info.plist"
            bid=(EXPECTED+".BAD" if wrong_id else EXPECTED)+("."+ext if ext else "")
            info={"CFBundleIdentifier":bid,"CFBundleVersion":"3.8.60",
                  "CFBundleShortVersionString":"3.8.11"}
            z.writestr(name,plistlib.dumps(info,fmt=plistlib.FMT_BINARY))
        z.writestr(APP+"LiveContainer",b"Binary\0\x1f\xff")
        sym=zipfile.ZipInfo(APP+"linked-resource")
        sym.create_system=3
        sym.external_attr=(0o120777<<16)
        z.writestr(sym,"../Resources")

class SideInstallerIdentity(unittest.TestCase):
    def test_sideinstaller_final_host_and_three_extensions_match_existing(self):
        with tempfile.TemporaryDirectory() as d:
            src,dst=Path(d)/"in.ipa",Path(d)/"out.ipa"
            make_ipa(src)
            mod.rebase_unsigned_ipa(src,dst,EXPECTED,TEAM,"3.8.60")
            with zipfile.ZipFile(src) as before,zipfile.ZipFile(dst) as after:
                self.assertIsNone(after.testzip())
                self.assertEqual(before.namelist(),after.namelist())
                main=plistlib.loads(after.read(APP+"Info.plist"))
                self.assertEqual(main["CFBundleIdentifier"],BASE)
                self.assertEqual(main["CFBundleIdentifier"]+"."+TEAM,EXPECTED)
                self.assertEqual(main["CFBundleVersion"],"3.8.60")
                for ext in mod.EXTENSIONS:
                    info=plistlib.loads(after.read(APP+"PlugIns/"+ext+".appex/Info.plist"))
                    self.assertEqual(info["CFBundleIdentifier"],BASE+"."+ext)
                    predicted=EXPECTED+info["CFBundleIdentifier"][len(BASE):]
                    self.assertEqual(predicted,EXPECTED+"."+ext)
                self.assertEqual(before.read(APP+"LiveContainer"),after.read(APP+"LiveContainer"))
                self.assertEqual(before.getinfo(APP+"linked-resource").external_attr,
                                 after.getinfo(APP+"linked-resource").external_attr)
    def test_bad_source_identity_fails_without_creating_partial_release(self):
        with tempfile.TemporaryDirectory() as d:
            src,dst=Path(d)/"bad.ipa",Path(d)/"out.ipa"
            make_ipa(src,wrong_id=True)
            with self.assertRaises(ValueError):
                mod.rebase_unsigned_ipa(src,dst,EXPECTED,TEAM,"3.8.60")
            self.assertFalse(dst.exists())
    def test_wrong_team_build_or_in_place_writes_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            src,dst=Path(d)/"valid.ipa",Path(d)/"out.ipa"
            make_ipa(src)
            for args in [(EXPECTED,"DIFFERENT","3.8.60"),
                         (EXPECTED,TEAM,"3.8.11")]:
                with self.subTest(args=args), self.assertRaises(ValueError):
                    mod.rebase_unsigned_ipa(src,dst,*args)
            with self.assertRaises(ValueError):
                mod.rebase_unsigned_ipa(src,src,EXPECTED,TEAM,"3.8.60")
    def test_p60_ci_verifies_source_and_predicted_installed_ids(self):
        for value in (
            "SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.60)",
            "prepare_sideinstaller_ipa.py",
            "--installed-host-id com.kdt.livecontainer.P8EZT3U5N4",
            "--team-id P8EZT3U5N4",
            "--build 3.8.60",
            'assert info["CFBundleIdentifier"]=="com.kdt.livecontainer"',
            "scarlet-v48-r6p60-sideinstaller-unsigned-20261114",
            "Scarlet-Crystal-V48-R6P60-SIDEINSTALLER-UNSIGNED.ipa"
        ):
            self.assertIn(value,WF,value)

if __name__=="__main__":
    unittest.main()
