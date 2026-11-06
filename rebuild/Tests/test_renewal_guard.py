import datetime as dt
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "renewal",ROOT/"signing/renewal_guard.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
now=dt.datetime(2026,11,6,tzinfo=dt.timezone.utc)


def profiles(expires):
    return [{
        "bundle":bundle,
        "entitlements":{
            "application-identifier":"P8EZT3U5N4."+bundle,
            "com.apple.security.application-groups":["group.scarlet.internal"],
            "get-task-allow":True
        },
        "teams":["P8EZT3U5N4"],
        "expires":expires,
        "provisioned_devices":True
    } for bundle in sorted(m.REQUIRED)]


class RenewalGateTests(unittest.TestCase):
    def test_valid_until_96h_window(self):
        result=m.decide(profiles(now+dt.timedelta(hours=100)),now)
        self.assertEqual(result["state"],"valid")
        self.assertFalse(result["free_personal_team_seven_day_limit_removed"])
        self.assertFalse(result["automatic_ios_install_verified"])

    def test_renew_before_expiry(self):
        result=m.decide(profiles(now+dt.timedelta(hours=72)),now)
        self.assertEqual(result["state"],"renewal_due")
        self.assertEqual(result["remaining_hours"],72)

    def test_expired_is_not_renewed_by_app_update(self):
        result=m.decide(profiles(now-dt.timedelta(minutes=5)),now)
        self.assertEqual(result["state"],"expired")
        self.assertFalse(result["automatic_ios_install_verified"])

    def test_one_earlier_extension_expiration_controls_all(self):
        ps=profiles(now+dt.timedelta(days=5))
        ps[-1]["expires"]=now+dt.timedelta(hours=24)
        self.assertEqual(m.decide(ps,now)["state"],"renewal_due")

    def test_one_missing_extension_blocks(self):
        ps=profiles(now+dt.timedelta(days=6))
        ps.pop()
        r=m.decide(ps,now)
        self.assertEqual(r["state"],"blocked")
        self.assertIn("bundle_set_mismatch",r["blocking_categories"])

    def test_missing_app_group_blocks_before_signing(self):
        ps=profiles(now+dt.timedelta(days=6))
        ps[0]["entitlements"].pop("com.apple.security.application-groups")
        r=m.decide(ps,now)
        self.assertEqual(r["state"],"blocked")
        self.assertIn("missing_app_group",r["blocking_categories"])

    def test_unregistered_device_and_mismatch_block(self):
        ps=profiles(now+dt.timedelta(days=6))
        ps[0]["provisioned_devices"]=False
        ps[1]["entitlements"]["application-identifier"]="someone.else"
        flags=m.decide(ps,now)["blocking_categories"]
        self.assertIn("no_device_registration",flags)
        self.assertIn("bundle_entitlement_mismatch",flags)

    def test_no_profile_is_error_not_success(self):
        with self.assertRaises(ValueError):
            m.decide([],now)


if __name__=="__main__":
    unittest.main()
