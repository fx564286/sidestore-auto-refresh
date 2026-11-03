"""V177: pinned composition follows both actual upstreams, not a mixed SHA."""
from pathlib import Path
import importlib.util
import json
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upfollow", ROOT/"scripts/scarlet_upstream_follow.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
a, b, c, d, e = ["1"*40, "2"*40, "3"*40, "4"*40, "5"*40]
BASE = (
    "env:\n"
    f"  LIVE_CONTAINER_REF: {a}\n"
    f"  EMBEDDED_SIDESTORE_REF: {b}\n"
    f"  MINIMUXER_REF: {c}\n"
    f"  SIDESIGN_REF: {d}\n"
    "  IDEVICE_REF: " + "a"*40 + "\n"
)

def fake_api(url):
    if url.endswith("/LiveContainer/commits/main"):
        return {"sha": e}
    if url.endswith("/SideStore/commits/LiveContainerSupport"):
        return {"sha": d}
    if "/LiveContainer/SideStore/git/trees/" in url:
        return {"truncated": False, "tree": [
            {"path": "Dependencies/minimuxer", "mode": "160000", "type": "commit", "sha": c},
            {"path": "Dependencies/SideSign", "mode": "160000", "type": "commit", "sha": b}
        ]}
    if url.endswith("/SideStore/commits/develop"):
        return {"sha": a}
    raise AssertionError("Unexpected URL: " + url)

class UpstreamFollowTests(unittest.TestCase):
    def test_both_actual_parents_and_nested_gitlinks(self):
        with patch.object(module, "api_get", side_effect=fake_api):
            actual, advisory = module.discover()
        self.assertEqual(actual, {
            "LIVE_CONTAINER_REF": e,
            "EMBEDDED_SIDESTORE_REF": d,
            "MINIMUXER_REF": c,
            "SIDESIGN_REF": b,
        })
        self.assertEqual(advisory, a)

    def test_rewrite_only_exact_source_pins(self):
        newer = {"LIVE_CONTAINER_REF": e, "EMBEDDED_SIDESTORE_REF": d,
                 "MINIMUXER_REF": c, "SIDESIGN_REF": b}
        changed = module.propose(BASE, newer)
        self.assertEqual(module.propose(changed, newer), changed)
        self.assertIn("  IDEVICE_REF: " + "a"*40, changed)
        for key, value in newer.items():
            self.assertEqual(module.pinned(changed, key), value)
        with self.assertRaises(ValueError):
            module.propose(BASE, {"IDEVICE_REF": e})

    def test_json_source_of_truth_changes_only_verified_four_refs(self):
        original = json.dumps({
            "LIVE_CONTAINER_REF": a,
            "EMBEDDED_SIDESTORE_REF": b,
            "MINIMUXER_REF": c,
            "SIDESIGN_REF": d
        }) + "\n"
        next_refs = {"LIVE_CONTAINER_REF": e,
                     "EMBEDDED_SIDESTORE_REF": d,
                     "MINIMUXER_REF": c,
                     "SIDESIGN_REF": b}
        changed = module.propose(original, next_refs)
        self.assertEqual(module.propose(changed, next_refs), changed)
        self.assertEqual(json.loads(changed), next_refs)
        for key, value in next_refs.items():
            self.assertEqual(module.pinned(changed, key), value)
        with self.assertRaises(ValueError):
            module.propose(original, {"LIVE_CONTAINER_REF": e})
        with self.assertRaises(ValueError):
            module.pinned(json.dumps({"LIVE_CONTAINER_REF": a}), "LIVE_CONTAINER_REF")

    def test_advisory_not_integrated(self):
        record = module.make_report(BASE, {
            "LIVE_CONTAINER_REF": e, "EMBEDDED_SIDESTORE_REF": d,
            "MINIMUXER_REF": c, "SIDESIGN_REF": b,
        }, a)
        self.assertTrue(record["needs_rebase"])
        self.assertFalse(record["auto_release"])
        self.assertEqual(record["sidestore_develop_advisory"]["head"], a)

    def test_missing_submodule_is_fatal(self):
        def missing(url):
            result = fake_api(url)
            if "/git/trees/" in url:
                result["tree"] = []
            return result
        with patch.object(module, "api_get", side_effect=missing):
            with self.assertRaisesRegex(ValueError, "gitlink"):
                module.discover()

    def test_duplicate_pin_is_fatal(self):
        with self.assertRaises(ValueError):
            module.pinned(BASE + "  LIVE_CONTAINER_REF: " + a + "\n",
                          "LIVE_CONTAINER_REF")

if __name__ == "__main__":
    unittest.main()
