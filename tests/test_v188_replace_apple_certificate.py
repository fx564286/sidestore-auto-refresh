"""Offline safety tests for approved one-certificate replacement; never call Apple."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main, mock

SOURCE=Path(__file__).resolve().parents[1]/"scripts/scarlet_v188_replace_apple_certificate.py"
spec=importlib.util.spec_from_file_location("v188_replace",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class AppleFake:
    def __init__(self,group=True):
        self.names=[]
        self.group=group
    def call(self,name,body=None,key=None,device_type=None):
        self.names.append(name)
        if name=="listTeams":
            return [{"teamId":m.TEAM,"type":"Individual"}]
        if name=="listAppIds":
            return {"appIds":[{"identifier":x,"appIdId":str(i),
                               "features":{"APG3427HIY":True}}
                              for i,x in enumerate(m.BUNDLES)]}
        if name=="listApplicationGroups":
            return [{"identifier":m.GROUP}] if self.group else []
        if name=="listAllDevelopmentCerts":
            return []
        raise AssertionError("Unexpected API request: "+name)

class CertificateReplacementTests(TestCase):
    def test_fixed_identity_scope(self):
        self.assertEqual(m.TEAM,"P8EZT3U5N4")
        self.assertEqual(m.GROUP,"group.com.SideStore.SideStore.P8EZT3U5N4")
        self.assertEqual(len(m.BUNDLES),4)
        self.assertEqual(set(m.BUNDLES),
          {m.APP,m.APP+".LiveProcess",m.APP+".ShareExtension",m.APP+".LaunchAppExtension"})

    def test_missing_key_stops_before_revoke(self):
        with TemporaryDirectory() as td:
            with mock.patch.object(m,"KEY",Path(td)/"missing.pem"):
                with self.assertRaisesRegex(RuntimeError,"PREVIOUSLY_CREATED_PRIVATE_KEY_MISSING"):
                    m.public_key_local()

    def test_app_group_and_bundle_preflight_is_read_only(self):
        with TemporaryDirectory() as td:
            f=Path(td)/"profile-0.mobileprovision";f.write_bytes(b"opaque")
            with mock.patch.object(m,"BACKUP",Path(td)):
                fake=AppleFake()
                self.assertEqual(set(m.safe_four_app_ids(fake)),set(m.BUNDLES))
                self.assertEqual(fake.names,
                                 ["listTeams","listAppIds","listApplicationGroups"])

    def test_group_loss_blocks_before_revocation(self):
        with TemporaryDirectory() as td:
            (Path(td)/"profile-0.mobileprovision").write_bytes(b"opaque")
            with mock.patch.object(m,"BACKUP",Path(td)):
                fake=AppleFake(group=False)
                with self.assertRaisesRegex(RuntimeError,"ORIGINAL_APP_GROUP_MISSING"):
                    m.safe_four_app_ids(fake)
                self.assertNotIn("revokeDevelopmentCert",fake.names)

    def test_previous_csr_submission_never_repeated(self):
        fake=AppleFake()
        state={"csr_submitted":True}
        with mock.patch.object(m,"list_certs",return_value=[]),mock.patch.object(m,"matching_cert",return_value=None):
            with self.assertRaisesRegex(RuntimeError,"CSR_PREVIOUSLY_SUBMITTED"):
                m.enroll_after_revoke(fake,b"PUBLIC",state,None)
        self.assertNotIn("submitDevelopmentCSR",fake.names)

    def test_unexpected_active_cert_blocks_csr(self):
        fake=AppleFake()
        state={"csr_submitted":False}
        with mock.patch.object(m,"list_certs",return_value=[{"serialNumber":"OTHER"}]),mock.patch.object(m,"matching_cert",return_value=None):
            with self.assertRaisesRegex(RuntimeError,"OLD_OR_OTHER_CERT_STILL_REGISTERED"):
                m.enroll_after_revoke(fake,b"PUBLIC",state,None)
        self.assertNotIn("submitDevelopmentCSR",fake.names)

    def test_revoke_target_only_after_old_profile_verify(self):
        s=SOURCE.read_text()
        self.assertLess(s.index("assert_old_cert_used_by_all_four(reconciler,old_der,old)"),
                        s.index('session.call("revokeDevelopmentCert"'))
        self.assertLess(s.index("archive_old_public_cert(old,old_der)"),
                        s.index('session.call("revokeDevelopmentCert"'))
        self.assertIn('"serialNumber":st["old_serial"]',s)
        self.assertIn("CSR_PREVIOUSLY_SUBMITTED",s)

if __name__=="__main__":
    main()
