"""Regression coverage for applying host scene changes to two independent guests."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REBUILD = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "scarlet_host", REBUILD / "integration" / "apply_scarlet_host.py")
HOST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)

ORIGINAL = ("    UIMutableApplicationSceneSettings *baseSettings = "
            "[diff settingsByApplyingToMutableCopyOfSettings:settings];")
SCENE = "MultitaskSupport/AppSceneViewController.m"
ENGINE = os.environ.get("SCARLET_TEST_GENERATED_ENGINE")


def diff_callback(source):
    start = source.index("- (void)_performActionsForUIScene:")
    end = source.index("\n}", start) + 2
    return source[start:end]


class ResidentSceneSettingsTests(unittest.TestCase):
    def test_integration_rejects_a_missing_or_ambiguous_pinned_callback(self):
        for source in ("", ORIGINAL + "\n" + ORIGINAL):
            with self.subTest(source=source), self.assertRaises(ValueError):
                HOST.repair_resident_scene_settings(source)

    def test_only_changed_lifecycle_orientation_and_style_reach_the_guest(self):
        code = (diff_callback((Path(ENGINE) / SCENE).read_text()) if ENGINE else
                HOST.repair_resident_scene_settings(ORIGINAL))
        resident, legacy = code.split("    } else {", 1)
        self.assertIn("scene != self.viewIfLoaded.window.windowScene", resident)
        self.assertIn("baseSettings = [self.presenter.scene.settings mutableCopy];", resident)
        self.assertIn("if (!baseSettings || !before || !after) return;", resident)
        self.assertIn("baseSettings = [diff settingsByApplyingToMutableCopyOfSettings:settings];",
                      legacy)
        writes = re.findall(r"baseSettings\.(\w+)\s*=", resident)
        expected = {"foreground", "deactivationReasons", "interfaceOrientation",
                    "deviceOrientation", "userInterfaceStyle"}
        self.assertCountEqual(writes, expected)
        for field in expected:
            self.assertIn(f"if (before.{field} != after.{field}) {{\n"
                          f"            baseSettings.{field} = after.{field};", resident)

    @unittest.skipUnless(sys.platform == "darwin" and ENGINE, "requires the generated macOS CI checkout")
    def test_native_callback_with_two_guests_and_foreign_host_transitions(self):
        engine = Path(ENGINE).resolve()
        original = subprocess.check_output(
            ["git", "-C", str(engine), "show", "HEAD:" + SCENE], text=True)
        harness = REBUILD / "Tests" / "fixtures" / "resident_scene_settings.m"
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            for name, source in (("pinned", original), ("integrated", (engine / SCENE).read_text())):
                with self.subTest(source=name):
                    (work / "SceneCallback.inc").write_text(diff_callback(source))
                    binary = work / name
                    subprocess.run(["xcrun", "--sdk", "macosx", "clang", "-fobjc-arc",
                                    "-framework", "Foundation", "-I", str(work),
                                    str(harness), "-o", str(binary)], check=True)
                    result = subprocess.run([str(binary)], capture_output=True, text=True)
                    if name == "pinned":
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertIn("guest identity replaced", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
