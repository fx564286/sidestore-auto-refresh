"""Read-only signed IPA verification: 4 bundles and historical rights."""
import datetime as dt
import pathlib
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import scarlet_entitlement_recovery as core
import scarlet_signed_ipa_audit as mod

def baseline():
    return {"application-identifier":core.TEAM+"."+core.MAIN,
            "com.apple.developer.team-identifier":core.TEAM,
            core.KEYCHAINS:[core.TEAM+".com.scarlet"],
            core.GROUPS:["group.scarlet"],core.MEMORY:True}

def profile(bundle):
    return {"application-identifier":core.TEAM+"."+bundle,
            "com.apple.developer.team-identifier":core.TEAM,
            core.KEYCHAINS:[core.TEAM+".*"],
            core.GROUPS:["group.scarlet"],core.MEMORY:True}

class SignedIpaAuditTests(unittest.TestCase):
    def test_host_rights_match(self):
        mod.match_declared_entitlements(core.MAIN,baseline(),profile(core.MAIN),baseline())

    def test_host_entitlements_must_match_existing(self):
        changed=baseline();changed[core.KEYCHAINS]=[core.TEAM+".other"]
        with self.assertRaisesRegex(core.Halt,"historical baseline"):
            mod.match_declared_entitlements(core.MAIN,changed,profile(core.MAIN),baseline())

    def test_extension_rights_must_be_authorized(self):
        bid=core.MAIN+".ShareExtension"
        signed={"application-identifier":core.TEAM+"."+bid,
                "com.apple.developer.team-identifier":core.TEAM,
                core.GROUPS:["group.unapproved"]}
        with self.assertRaisesRegex(core.Halt,"not authorized"):
            mod.match_declared_entitlements(bid,signed,profile(bid))

    def test_extension_application_identifier_cannot_be_swapped(self):
        bid=core.MAIN+".ShareExtension"
        signed={"application-identifier":core.TEAM+"."+core.MAIN,
                "com.apple.developer.team-identifier":core.TEAM}
        with self.assertRaisesRegex(core.Halt,"identifier mismatch"):
            mod.match_declared_entitlements(bid,signed,profile(bid))

    def test_full_four_bundle_structure_with_mocked_profile_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            baseline_file=root/"entitlements.xml"
            baseline_file.write_bytes(plistlib.dumps(baseline()))
            ipa=root/"app.ipa"
            records={}
            with zipfile.ZipFile(ipa,"w") as z:
                for bid in sorted(core.BUNDLES):
                    if bid==core.MAIN:
                        folder="Payload/LiveContainer.app/"
                        ent=baseline()
                    else:
                        ext=bid.rsplit(".",1)[-1]
                        folder=f"Payload/LiveContainer.app/PlugIns/{ext}.appex/"
                        ent={"application-identifier":core.TEAM+"."+bid,
                             "com.apple.developer.team-identifier":core.TEAM,
                             core.KEYCHAINS:[core.TEAM+".com.scarlet"]}
                    executable=bid.rsplit(".",1)[-1]
                    z.writestr(folder+"Info.plist",plistlib.dumps({
                        "CFBundleIdentifier":bid,"CFBundleExecutable":executable}))
                    z.writestr(folder+executable,bid.encode())
                    z.writestr(folder+"embedded.mobileprovision",bid.encode())
                    records[bid]=ent
            with patch.object(mod,"verify_profile",side_effect=lambda data,bundle,*_:profile(bundle)), \
                 patch.object(mod,"ldid_entitlements",side_effect=lambda blob:records[blob.decode()]):
                result=mod.audit(ipa,baseline_file,b"cert","example-udid")
            self.assertEqual(result,sorted(core.BUNDLES))

    def test_reject_missing_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            baseline_file=path/"entitlements.plist"
            baseline_file.write_bytes(plistlib.dumps(baseline()))
            ipa=path/"short.ipa"
            with zipfile.ZipFile(ipa,"w") as z:
                z.writestr("Payload/LiveContainer.app/Info.plist",plistlib.dumps({
                    "CFBundleIdentifier":core.MAIN,"CFBundleExecutable":"LiveContainer"}))
            with self.assertRaisesRegex(core.Halt,"four"):
                mod.audit(ipa,baseline_file,b"cert","test-udid")

if __name__=="__main__":
    unittest.main()
