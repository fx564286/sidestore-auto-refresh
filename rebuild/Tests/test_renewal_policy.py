"""Strict 7-day free Personal Team signing/profile refresh decision tests."""
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

FILE=Path(__file__).resolve().parents[1]/"tools"/"renewal_policy.py"
spec=importlib.util.spec_from_file_location("scarlet_refresh",FILE)
refresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(refresh)
NOW=dt.datetime(2026,11,6,0,0,tzinfo=dt.timezone.utc)

def snapshot(hours=95):
    return {
        "team_id":refresh.TEAM,
        "bundle_id":refresh.HOST,
        "profiles":[{
            "bundle_id":name,
            "expires_at":(NOW+dt.timedelta(hours=hours)).isoformat(),
            "profile_kind":"development",
            "app_group_authorized":True,
            "identity_matches":True,
            "device_registered":True,
            "cms_verified":True,
            "certificate_authorized":True,
        } for name in refresh.BUNDLES]
    }

class RenewalTests(unittest.TestCase):
    def test_valid_profiles_no_unnecessary_refresh(self):
        state=refresh.evaluate(snapshot(95),NOW)
        self.assertEqual(state["status"],"VALID")
        self.assertFalse(state["needs_refresh"])
        self.assertFalse(state["refresh_completed"])
        self.assertFalse(state["installation_verified"])

    def test_under_72_hours_requires_refresh_not_claimed_success(self):
        state=refresh.evaluate(snapshot(48),NOW)
        self.assertEqual(state["status"],"REFRESH_DUE")
        self.assertTrue(state["local_refresh_preflight_ready"])
        self.assertFalse(state["refresh_completed"])
        self.assertFalse(state["installation_verified"])
        self.assertIn("development",state["next_actions"][0])

    def test_expiry_cannot_be_bypassed(self):
        state=refresh.evaluate(snapshot(-1),NOW)
        self.assertEqual(state["status"],"EXPIRED")
        self.assertTrue(state["needs_refresh"])
        self.assertFalse(state["refresh_completed"])

    def test_missing_fourth_profile_is_rejected(self):
        s=snapshot();s["profiles"].pop()
        with self.assertRaisesRegex(ValueError,"four"):refresh.evaluate(s,NOW)

    def test_duplicate_profile_is_rejected(self):
        s=snapshot();s["profiles"][0]["bundle_id"]=refresh.BUNDLES[1]
        with self.assertRaisesRegex(ValueError,"duplicated"):refresh.evaluate(s,NOW)

    def test_app_group_gap_blocks_refresh(self):
        s=snapshot(25);s["profiles"][3]["app_group_authorized"]=False
        state=refresh.evaluate(s,NOW)
        self.assertEqual(state["status"],"BLOCKED")
        self.assertFalse(state["local_refresh_preflight_ready"])
        self.assertIn("app_group_authorized",{x["reason"] for x in state["refused_conditions"]})

    def test_missing_verification_must_not_be_inferred(self):
        for check in ("app_group_authorized","identity_matches","device_registered",
                      "cms_verified","certificate_authorized"):
            s=snapshot(25);del s["profiles"][0][check]
            self.assertEqual(refresh.evaluate(s,NOW)["status"],"BLOCKED")

    def test_development_only_does_not_auto_enable_ad_hoc(self):
        s=snapshot(24);s["profiles"][1]["profile_kind"]="ad_hoc"
        self.assertEqual(refresh.evaluate(s,NOW)["status"],"BLOCKED")

    def test_identity_and_timezone_strict(self):
        s=snapshot();s["team_id"]="WRONG"
        with self.assertRaisesRegex(ValueError,"identity"):refresh.evaluate(s,NOW)
        s=snapshot();s["profiles"][0]["expires_at"]="2026-11-11T02:00:00"
        with self.assertRaisesRegex(ValueError,"timezone"):refresh.evaluate(s,NOW)

if __name__=="__main__":unittest.main()
