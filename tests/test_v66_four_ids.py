"""V66: verify 4-App-ID packaging and host-owned Launch App shortcuts."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V66FourAppIdsTests(unittest.TestCase):
    def setUp(self):
        self.script = load("patch_v66_four_ids")
        self.packager = load("package_livecontainer_combined")

    def test_main_app_contains_shortcuts_intent_and_validates_url(self):
        code = self.script.SWIFT
        for required in ("struct ScarletCrystalLaunchAppIntent: AppIntent",
                         'static var openAppWhenRun: Bool { true }',
                         "@Parameter(title: \"Launch URL\")",
                         "UIApplication.shared.open(launchURL",
                         'parts.host?.lowercased() == "livecontainer-launch"'):
            self.assertIn(required, code)

    def test_pbxproj_patch_is_repeatable(self):
        original = os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not original or not Path(original, "LiveContainer.xcodeproj", "project.pbxproj").is_file():
            self.skipTest("The pinned LiveContainer source is required for project patch integration")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "LiveContainer.xcodeproj").mkdir()
            (root / "LiveContainer").mkdir()
            pristine = subprocess.check_output([
                'git', '-C', original, 'show', 'HEAD:LiveContainer.xcodeproj/project.pbxproj'])
            (root / 'LiveContainer.xcodeproj' / 'project.pbxproj').write_bytes(pristine)
            self.script.patch(root)
            p = root / "LiveContainer.xcodeproj" / "project.pbxproj"
            first = p.read_bytes()
            self.script.patch(root)
            self.assertEqual(first, p.read_bytes())
            self.assertEqual(p.read_text().count("NRG_V66_FOUR_IDS"), 1)
            self.assertTrue((root / "LiveContainer" / self.script.NAME).is_file())

    def test_packer_keeps_native_island_and_removes_launcher(self):
        upstream = os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not upstream or not Path(upstream, ".github/build_github.sh").is_file():
            self.skipTest("Pinned upstream packaging script required")
        content = Path(upstream, ".github/build_github.sh").read_text()
        with patch.dict(os.environ, {"NRG_V58_NATIVE_ISLAND": "1", "NRG_V66_4IDS": "1"}):
            output = self.packager.adapt(content)
        self.assertIn("rm -rf ./Payload/LiveContainer.app/PlugIns/LaunchAppExtension.appex", output)
        self.assertIn("--merge-host-intents", output)
        self.assertIn("LiveWidgetExtension.appex", output)
        self.assertIn("'PlugIns/ShareExtension.appex': 'ShareExtension/ShareExtension.entitlements'",
                      (ROOT / 'scripts/package_livecontainer_combined.py').read_text())
        with patch.dict(os.environ, {"NRG_V58_NATIVE_ISLAND": "1"}, clear=True):
            baseline = self.packager.adapt(content)
        self.assertNotIn("--merge-host-intents", baseline)
        self.assertNotIn("rm -rf ./Payload/LiveContainer.app/PlugIns/LaunchAppExtension.appex", baseline)

    def test_merge_preserves_generated_shortcut_action_identifiers(self):
        # Real SideStore action names are Xcode-extracted, not necessarily Swift
        # type names. Reproduces the V67 macOS CI failure #39728166811.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            actions_file = root / "Metadata.appintents" / "extract.actionsdata"
            actions_file.parent.mkdir()
            side_actions = {
                "RefreshAllIntent": {"mangledTypeNameV2": "16SideStoreSupport20RefreshAllAppsIntentV"},
                "RefreshAllWidgetIntent": {"mangledTypeNameV2": "16SideStoreSupport26RefreshAllAppsWidgetIntentV"},
            }
            actions_file.write_text(json.dumps({"version": 1, "actions": side_actions,
                                                "enums": [], "entities": {}, "queries": {}}))
            host = root / "host.json"
            host.write_text(json.dumps({"version": 1,
                                        "actions": {"ScarletCrystalLaunchAppIntent": {"mangledTypeNameV2": "native"}},
                                        "enums": [{"case": "example"}], "entities": {}}))
            self.packager.merge_host_intents(root, host)
            merged = json.loads(actions_file.read_text())
            self.assertEqual(set(merged["actions"]),
                             {"RefreshAllIntent", "RefreshAllWidgetIntent", "ScarletCrystalLaunchAppIntent"})
            self.assertEqual(merged["actions"]["RefreshAllIntent"], side_actions["RefreshAllIntent"])
            self.assertEqual(merged["enums"], [{"case": "example"}])

    def test_merge_rejects_missing_side_store_runtime_or_overwriting_intents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            actions_file = root / "Metadata.appintents" / "extract.actionsdata"
            actions_file.parent.mkdir()
            host = root / "host.json"
            host.write_text(json.dumps({"actions": {"ScarletCrystalLaunchAppIntent": {"mangledTypeNameV2": "native"}}}))
            actions_file.write_text(json.dumps({"actions": {"Unknown": {"mangledTypeNameV2": "not SIDESTORE"}}}))
            with self.assertRaisesRegex(ValueError, "runtime action marker missing"):
                self.packager.merge_host_intents(root, host)

    def test_ci_checks_current_minimum_feature_packaging(self):
        workflow = (ROOT / '.github/workflows/livecontainer-build.yml').read_text()
        self.assertIn('python3 builder/scripts/patch_v66_four_ids.py work/LiveContainer', workflow)
        if 'v68_appid_minimizer.py' in workflow:
            self.assertIn('builder/config/v68_required_features.json', workflow)
            self.assertIn("expected=set(plan['expected_unsigned_bundle_ids'][1:])", workflow)
        elif 'NRG_V67_3IDS: "1"' in workflow:
            self.assertIn("('LiveProcess','LiveWidget')", workflow)
        else:
            self.assertIn("('LiveProcess','ShareExtension','LiveWidget')", workflow)
        self.assertNotIn("('LiveProcess','ShareExtension','LaunchAppExtension','LiveWidget')", workflow.split('PY_WIDGET',1)[0])


if __name__ == "__main__":
    unittest.main()
