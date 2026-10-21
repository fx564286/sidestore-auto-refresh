"""Prevent the signed app and user-visible Dynamic Island from drifting in name."""
import plistlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "Scarlet Crystal"


class AppBrandingTests(unittest.TestCase):
    def test_host_metadata_stamping_and_final_package(self):
        workflow = (ROOT / ".github/workflows/livecontainer-build.yml").read_text()
        self.assertIn("info['CFBundleDisplayName']='Scarlet Crystal'", workflow)
        self.assertIn("info['CFBundleName']='Scarlet Crystal'", workflow)
        self.assertIn("assert main.get('CFBundleDisplayName')=='Scarlet Crystal'", workflow)
        self.assertNotIn("Scarlet & Crystal", workflow)

    def test_early_startup_branding(self):
        script = (ROOT / "scripts/patch_v192_startup.py").read_text()
        self.assertIn('info["CFBundleDisplayName"]="Scarlet Crystal"', script)
        self.assertIn('info["CFBundleName"]="Scarlet Crystal"', script)

    def test_island_and_host_home_label(self):
        native = (ROOT / "scripts/patch_v58_native_activity.py").read_text()
        self.assertIn('Text("Scarlet Crystal")', native)
        self.assertIn('Label("Scarlet Crystal", systemImage:', native)
        self.assertIn('Label("Scarlet Crystal 열기", systemImage:', native)
        self.assertNotIn("Scarlet & Crystal", native)

    def test_webclip_bookmark_name_matches(self):
        path = ROOT / "delivery/Scarlet-Crystal-Install.mobileconfig"
        info = plistlib.loads(path.read_bytes())
        self.assertEqual(info["PayloadDisplayName"], NAME)
        self.assertEqual(info["PayloadContent"][0]["Label"], NAME)
        self.assertEqual(info["PayloadContent"][0]["PayloadType"], "com.apple.webClip.managed")

    def test_no_legacy_brand_in_shipped_source(self):
        paths = [
            ROOT / ".github/workflows/livecontainer-build.yml",
            ROOT / "scripts/patch_v192_startup.py",
            ROOT / "scripts/patch_v58_native_activity.py",
            ROOT / "delivery/Scarlet-Crystal-Install.mobileconfig",
        ]
        for path in paths:
            with self.subTest(path=path.name):
                source = path.read_text()
                self.assertNotIn("Scarlet & Crystal", source)
                self.assertNotIn("Scarlet &amp; Crystal", source)


if __name__ == "__main__":
    unittest.main()
