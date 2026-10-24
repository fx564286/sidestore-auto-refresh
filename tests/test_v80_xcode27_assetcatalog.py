"""Xcode 27.2 RC SideStore asset catalog copy-collision regression."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("assetfix", ROOT / "scripts/patch_v80_xcode27_icons_catalog.py")
assetfix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assetfix)

class Xcode27AssetCatalogTests(unittest.TestCase):
    def test_pinned_altstore_project_can_be_rewritten_exactly_once(self):
        old = (f'{assetfix.PIN} = {{isa = PBXFileSystemSynchronizedRootGroup; exceptions = (); '
               f'{assetfix.OLD_TAIL}\n')
        new = assetfix.patch(old)
        self.assertIn(assetfix.MARKER, new)
        self.assertIn("explicitFolders = (); path = AltStore;", new)
        self.assertEqual(assetfix.patch(new), new)
        self.assertNotEqual(new, old)

    def test_fail_closed_on_missing_or_ambiguous_group(self):
        with self.assertRaises(ValueError):
            assetfix.patch("not a project")
        broken = f'{assetfix.PIN} = {{isa = PBXFileSystemSynchronizedRootGroup; explicitFileTypes = {{}}; }};'
        with self.assertRaises(ValueError):
            assetfix.patch(broken)
        old = (f'{assetfix.PIN} = {{isa = PBXFileSystemSynchronizedRootGroup; exceptions = (); '
               f'{assetfix.OLD_TAIL}\n')
        with self.assertRaises(ValueError):
            assetfix.patch(old + old)

    def test_no_asset_deletion_and_exact_project_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / assetfix.PROJECT
            file.parent.mkdir(parents=True)
            before = (f'{assetfix.PIN} = {{isa = PBXFileSystemSynchronizedRootGroup; exceptions = (); '
                      f'{assetfix.OLD_TAIL}\n')
            file.write_text(before)
            assetfix.apply(root)
            after = file.read_text()
            self.assertEqual(after.replace(assetfix.NEW_TAIL, assetfix.OLD_TAIL), before)
            self.assertEqual(after.count(assetfix.MARKER), 1)
            assetfix.apply(root)
            self.assertEqual(file.read_text(), after)
            for prohibited in ("rm -rf", "shutil.rmtree", "EXCLUDED_SOURCE_FILE_NAMES"):
                self.assertNotIn(prohibited, (ROOT/"scripts/patch_v80_xcode27_icons_catalog.py").read_text())

if __name__ == "__main__":
    unittest.main()
