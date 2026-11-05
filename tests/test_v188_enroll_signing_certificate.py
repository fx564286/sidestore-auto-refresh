"""Offline regression tests for safe one-shot Scarlet V188 certificate enrollment."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main, mock

SRC=Path(__file__).resolve().parents[1]/"scripts/scarlet_v188_enroll_signing_certificate.py"
spec=importlib.util.spec_from_file_location("v188_enroll",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FakeApple:
    def __init__(self):
        self.calls=[]
    def call(self,name,body=None,key=None,device_type=None):
        self.calls.append(name)
        if name=="listTeams":
            return [{"teamId":m.TEAM,"type":"Individual"}]
        if name=="listAppIds":
            return {"appIds":[{"identifier":bundle,"appIdId":str(i),
                               "features":{"APG3427HIY":True}}
                              for i,bundle in enumerate(m.BUNDLES)]}
        if name=="listApplicationGroups":
            return [{"identifier":m.GROUP}]
        if name=="listAllDevelopmentCerts":
            return [{"certContent":b"placeholder"}]
        raise AssertionError("Unexpected Apple mutation: "+name)

class EnrollmentTests(TestCase):
    def test_existing_four_app_ids_are_read_only(self):
        api=FakeApple()
        apps=m.verify_existing_apple_state(api)
        self.assertEqual(set(apps),set(m.BUNDLES))
        self.assertEqual(api.calls,["listTeams","listAppIds","listApplicationGroups"])
    def test_missing_app_group_blocks_before_enrollment(self):
        api=FakeApple()
        original=api.call
        def no_group(name,*args,**kwargs):
            if name=="listApplicationGroups":
                return []
            return original(name,*args,**kwargs)
        api.call=no_group
        with self.assertRaisesRegex(RuntimeError,"EXISTING_APP_GROUP_NOT_FOUND"):
            m.verify_existing_apple_state(api)
    def test_one_shot_guard_prevents_duplicate_csr(self):
        with TemporaryDirectory() as td:
            p=Path(td)
            with mock.patch.object(m,"IDENTITY",p),mock.patch.object(m,"KEY",p/"private-key.pem"),mock.patch.object(m,"CERT",p/"certificate.pem"),mock.patch.object(m,"ATTEMPT",p/"csr-request-attempted.txt"):
                m.KEY.write_text("existing key")
                m.ATTEMPT.write_text("already attempted")
                with mock.patch.object(m,"find_issued_certificate",return_value=None):
                    with self.assertRaisesRegex(RuntimeError,"CSR_PREVIOUSLY_SUBMITTED"):
                        m.enroll_or_reuse_cert(FakeApple(),None)
    def test_no_certificate_revoke_or_appid_mutation(self):
        src=SRC.read_text()
        for forbidden in ['session.call("revoke', 'session.call("deleteAppId"',
                          'session.call("addAppId"', 'session.call("assignApplicationGroup']:
            self.assertNotIn(forbidden,src)
        self.assertIn("CSR_PREVIOUSLY_SUBMITTED_BUT_CERT_NOT_LISTED",src)
        self.assertIn("APPLE_CERTIFICATE_SLOT_UNCONFIRMED",src)
    def test_exact_four_bundle_ids(self):
        self.assertEqual(m.BUNDLES,[
            "com.kdt.livecontainer.P8EZT3U5N4",
            "com.kdt.livecontainer.P8EZT3U5N4.LiveProcess",
            "com.kdt.livecontainer.P8EZT3U5N4.ShareExtension",
            "com.kdt.livecontainer.P8EZT3U5N4.LaunchAppExtension"])

if __name__=="__main__":
    main()
