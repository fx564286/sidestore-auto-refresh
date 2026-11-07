"""Offline regression tests for fail-closed Scarlet entitlement recovery."""
import datetime as dt
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scarlet_entitlement_recovery as m

def original_entitlements():
    return {
        "application-identifier": m.TEAM+"."+m.MAIN,
        "com.apple.developer.team-identifier": m.TEAM,
        m.KEYCHAINS: [m.TEAM+".groupA",m.TEAM+".groupB"],
        m.GROUPS: ["group.scarlet"],
        m.MEMORY: True,
    }

def profile(bundle,allow_group=True,allow_mem=True):
    e={"application-identifier":m.TEAM+"."+bundle,
       m.KEYCHAINS:[m.TEAM+".*"],
       m.GROUPS:["group.scarlet"] if allow_group else []}
    if allow_mem: e[m.MEMORY]=True
    return {"TeamIdentifier":[m.TEAM],
            "ExpirationDate":dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=3),
            "Entitlements":e}

class ScarletEntitlementRecoveryTests(unittest.TestCase):
    def test_valid_historical_entitlements(self):
        ent=original_entitlements()
        m.historical_host(ent)
        m.authorized(ent,profile(m.MAIN)["Entitlements"])

    def test_empty_original_groups_rejected(self):
        ent=original_entitlements();ent.pop(m.GROUPS)
        with self.assertRaisesRegex(m.Halt,"application-groups"):
            m.historical_host(ent)

    def test_profile_without_app_group_rejected(self):
        with self.assertRaisesRegex(m.Halt,"application-groups"):
            m.authorized(original_entitlements(),profile(m.MAIN,False)["Entitlements"])

    def test_profile_without_memory_rejected(self):
        with self.assertRaisesRegex(m.Halt,"memory"):
            m.authorized(original_entitlements(),profile(m.MAIN,True,False)["Entitlements"])

    def test_keychain_missing_rejected(self):
        p=profile(m.MAIN)["Entitlements"]
        p[m.KEYCHAINS]=[m.TEAM+".groupA"]
        with self.assertRaisesRegex(m.Halt,"keychain"):
            m.authorized(original_entitlements(),p)

    def test_full_recovery_creates_private_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ent=root/"historical-entitlements.xml"
            ent.write_bytes(plistlib.dumps(original_entitlements()))
            profiles=[];loaded={}
            for number,bundle in enumerate(sorted(m.BUNDLES)):
                file=root/("profile-%03d.mobileprovision"%number)
                file.write_bytes(str(number).encode())
                loaded[str(number).encode()]=profile(bundle)
                profiles.append(file)
            out=root/"safe"/"entitlements.xml"
            with patch.object(m,"cms_profile",side_effect=lambda file:loaded[file.read_bytes()]):
                kc,groups=m.recover(root,profiles,out,possible=[ent])
            self.assertEqual((kc,groups),(2,1))
            self.assertEqual(plistlib.loads(out.read_bytes()),original_entitlements())
            self.assertEqual(out.stat().st_mode & 0o777,0o600)
            with patch.object(m,"cms_profile",side_effect=lambda file:loaded[file.read_bytes()]):
                with self.assertRaisesRegex(m.Halt,"overwrite"):
                    m.recover(root,profiles,out,possible=[ent])

    def test_unapproved_rights_never_write_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ent=root/"entitlements.xml"
            ent.write_bytes(plistlib.dumps(original_entitlements()))
            profiles=[];loaded={}
            for number,bundle in enumerate(sorted(m.BUNDLES)):
                file=root/("profile-%03d.mobileprovision"%number)
                file.write_bytes(str(number).encode())
                loaded[str(number).encode()]=profile(bundle,False)
                profiles.append(file)
            out=root/"safe"/"entitlements.xml"
            with patch.object(m,"cms_profile",side_effect=lambda file:loaded[file.read_bytes()]):
                with self.assertRaisesRegex(m.Halt,"App Group"):
                    m.recover(root,profiles,out,possible=[ent])
            self.assertFalse(out.exists())

    def test_historical_missing_memory_rejected(self):
        ent=original_entitlements()
        ent.pop(m.MEMORY)
        with self.assertRaisesRegex(m.Halt, "increased-memory"):
            m.historical_host(ent)

    def test_conflicting_candidates_fail_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            first=original_entitlements()
            second=original_entitlements()
            second[m.KEYCHAINS]=[m.TEAM+".groupA",m.TEAM+".groupC"]
            p1=root/"first-entitlements.plist";p1.write_bytes(plistlib.dumps(first))
            p2=root/"second-entitlements.plist";p2.write_bytes(plistlib.dumps(second))
            profiles=[];loaded={}
            for number,bundle in enumerate(sorted(m.BUNDLES)):
                file=root/("profile-%03d.mobileprovision"%number)
                file.write_bytes(str(number).encode())
                loaded[str(number).encode()]=profile(bundle)
                profiles.append(file)
            out=root/"safe"/"entitlements.xml"
            with patch.object(m,"cms_profile",side_effect=lambda file:loaded[file.read_bytes()]):
                with self.assertRaisesRegex(m.Halt,"conflicting historic entitlement sources"):
                    m.recover(root,profiles,out,possible=[p1,p2])
            self.assertFalse(out.exists())

    def test_explicit_source_allows_disambiguation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ent=root/"known-entitlements.plist"
            ent.write_bytes(plistlib.dumps(original_entitlements()))
            profiles=[];loaded={}
            for number,bundle in enumerate(sorted(m.BUNDLES)):
                file=root/("profile-%03d.mobileprovision"%number)
                file.write_bytes(str(number).encode())
                loaded[str(number).encode()]=profile(bundle)
                profiles.append(file)
            out=root/"safe"/"entitlements.xml"
            with patch.object(m,"cms_profile",side_effect=lambda file:loaded[file.read_bytes()]):
                self.assertEqual(m.recover(root,profiles,out,possible=[ent]),(2,1))
            self.assertTrue(out.is_file())

    def test_expiry_check(self):
        p=profile(m.MAIN)
        p["ExpirationDate"]=dt.datetime(2020,1,1)
        with self.assertRaisesRegex(m.Halt,"expired"):
            m.profile_info(p)

    def test_profile_cache_autodetect(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/".local/state/scarlet-crystal-installer/auto-renew"
            x=base/"earlier";x.mkdir(parents=True)
            y=base/"latest";y.mkdir()
            for i in range(4):
                (x/f"profile-{i}.mobileprovision").write_bytes(b"1")
                (y/f"profile-{i}.mobileprovision").write_bytes(b"2")
            import os
            os.utime(x,(100,100))
            os.utime(y,(200,200))
            self.assertEqual(m.latest_profile_dir(Path(tmp)),y)

if __name__=="__main__":
    unittest.main()
