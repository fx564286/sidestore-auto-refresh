import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
script = ROOT/"upstream/watch.py"
spec = importlib.util.spec_from_file_location("scarlet_upstream_watch", script)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

a,b,c,d,e = ("1"*40,"2"*40,"3"*40,"4"*40,"5"*40)
base = {"LIVE_CONTAINER_REF": a, "EMBEDDED_SIDESTORE_REF": b,
        "MINIMUXER_REF": c, "SIDESIGN_REF": d}


def fake_api(url):
    if url.endswith("/LiveContainer/commits/main"):
        return {"sha": e}
    if url.endswith("/SideStore/commits/LiveContainerSupport"):
        return {"sha": b}
    if "/LiveContainer/SideStore/git/trees/" in url:
        return {"truncated": False, "tree": [
            {"path":"Dependencies/minimuxer", "mode":"160000", "type":"commit", "sha":c},
            {"path":"Dependencies/SideSign", "mode":"160000", "type":"commit", "sha":d}
        ]}
    if url.endswith("/SideStore/commits/develop"):
        return {"sha": a}
    raise AssertionError(url)


class SourceGraphTests(unittest.TestCase):
    def test_no_mixed_parent_gitlink_source(self):
        newer, advisory = m.discover(fake_api)
        self.assertEqual(newer["EMBEDDED_SIDESTORE_REF"], b)
        self.assertEqual(newer["SIDESIGN_REF"], d)
        self.assertEqual(newer["MINIMUXER_REF"], c)
        self.assertEqual(newer["LIVE_CONTAINER_REF"], e)
        self.assertEqual(advisory, a)
        self.assertNotEqual(newer["EMBEDDED_SIDESTORE_REF"], advisory)

    def test_current_pins_are_strict_and_atomic(self):
        from_repo = m.decode_pins((ROOT/"upstream/pins.json").read_text())
        self.assertEqual(set(from_repo), m.KEYS)
        for value in from_repo.values():
            m.validated_pin(value)
        with self.assertRaises(ValueError):
            m.decode_pins(json.dumps({"LIVE_CONTAINER_REF": a}))
        with self.assertRaises(ValueError):
            m.decode_pins(json.dumps({**base, "UNKNOWN": e}))
        with self.assertRaises(ValueError):
            m.validated_pin("dev")

    def test_missing_nested_sidesign_is_fatal(self):
        def no_sidesign(url):
            v = fake_api(url)
            if "/git/trees/" in url:
                v["tree"] = [v["tree"][0]]
            return v
        with self.assertRaisesRegex(ValueError, "SideSign"):
            m.discover(no_sidesign)

    def test_truncated_tree_is_fatal(self):
        def truncated(url):
            result = fake_api(url)
            if "/git/trees/" in url:
                result["truncated"] = True
            return result
        with self.assertRaisesRegex(ValueError, "truncated"):
            m.discover(truncated)

    def test_changes_are_proposal_only(self):
        newer, advisory = m.discover(fake_api)
        report = m.make_report(base, newer, advisory)
        self.assertTrue(report["needs_review"])
        self.assertFalse(report["automatic_unreviewed_release"])
        self.assertTrue(report["refs"]["LIVE_CONTAINER_REF"]["changed"])
        self.assertFalse(report["refs"]["SIDESIGN_REF"]["changed"])

    def test_no_change_never_promotes(self):
        report = m.make_report(base, dict(base), a)
        self.assertFalse(report["needs_review"])
        self.assertFalse(report["automatic_unreviewed_release"])

if __name__ == "__main__":
    unittest.main()
