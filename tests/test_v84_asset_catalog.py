"""V84 regression: preserve icons and prevent two producers of raw asset files."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/patch_v84_asset_catalog.py"


def module():
    spec = importlib.util.spec_from_file_location("v84", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fixture():
    return """/* Begin PBXBuildFile section */
/* End PBXBuildFile section */
/* Begin PBXFileReference section */
/* End PBXFileReference section */
BFD247612284B9A500981D42 = {
  children = (
    A8EEC8412F4B146A00F2436D /* AltStore */,
  );
};
\t\t\tchildren = (
\t\t\t\tA8EEC8412F4B146A00F2436D /* AltStore */,
A8EEC8CB2F4B146B00F2436D /* PBXFileSystemSynchronizedBuildFileExceptionSet */ = {
\t\t\tmembershipExceptions = (
\t\t\t\tInfo.plist,
\t\t\t);
\t\t\ttarget = BFD247692284B9A500981D42 /* SideStore */;
\t\t};
BFD247682284B9A500981D42 /* Resources */ = {
\t\t\tfiles = (
\t\t\t\tA84596F62F7DC4C90000B8CD /* SideStore.conf in Resources */,
\t\t\t);
\t\t};
"""


class V84AssetCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = module()

    def test_idempotence_explicit_compiler_and_no_asset_deletion(self):
        before = fixture()
        after = self.m.patch(before)
        self.assertEqual(self.m.patch(after), after)
        self.assertEqual(after.count(self.m.MARK), 1)
        self.assertEqual(after.count("folder.assetcatalog"), 1)
        self.assertEqual(after.count("Resources/Icons.xcassets,"), 1)
        self.assertIn("path = AltStore/Resources/Icons.xcassets;", after)
        self.assertIn("A84596F62F7DC4C90000B8CD", after)
        self.assertNotIn("rm -rf", after)

    def test_missing_parent_target_fails_closed(self):
        with self.assertRaises(ValueError):
            self.m.patch(fixture().replace("BFD247692284B9A500981D42", "WRONG"))

    def test_drifted_raw_copy_exception_fails_closed(self):
        with self.assertRaises(ValueError):
            self.m.patch(fixture().replace("Info.plist,", "Another.plist,"))

    def test_collision_fails_closed(self):
        with self.assertRaises(ValueError):
            self.m.patch(fixture() + self.m.FILE_ID)


class V85LeafAssetTests(unittest.TestCase):
    def test_exact_leaf_path_exclusions_and_replay(self):
        import tempfile
        m = module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Contents.json").write_text("{}")
            for i in range(32):
                (root / f"asset-{i}.png").write_bytes(b"fixture")
            patched = m.patch(fixture())
            excluded = m.exclude_leaf_assets(patched, root)
            self.assertIn(m.LEAF_MARK, excluded)
            self.assertEqual(m.exclude_leaf_assets(excluded, root), excluded)
            for p in root.iterdir():
                expected = '"Resources/Icons.xcassets/' + p.name + '",'
                self.assertEqual(excluded.count(expected), 1)
            self.assertNotIn("rm -rf", excluded)
            corrupted = excluded.replace('"Resources/Icons.xcassets/asset-10.png",', "")
            with self.assertRaises(ValueError):
                m.exclude_leaf_assets(corrupted, root)

    def test_incomplete_catalog_fails_closed(self):
        import tempfile
        m = module()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Contents.json").write_text("{}")
            with self.assertRaises(ValueError):
                m.exclude_leaf_assets(m.patch(fixture()), Path(tmp))


if __name__ == "__main__":
    unittest.main()
