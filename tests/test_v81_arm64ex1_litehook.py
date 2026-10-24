"""V81 iOS 27.2 RC regressions for exact upstream litehook DSC suffix patch."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v81_litehook", ROOT / "scripts/patch_v81_arm64ex1_litehook.py")
v81 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v81)

class V81LitehookTests(unittest.TestCase):
    def test_exact_upstream_suffix_order_and_idempotence(self):
        source = "prefix\n" + v81.ORIGINAL + '\t\t\t"_arm64",\n\t\t\t"_armv7s",\n'
        patched = v81.patch(source)
        self.assertEqual(patched.count(v81.MARKER), 1)
        self.assertLess(patched.index(v81.MARKER), patched.index('"_arm64e",'))
        self.assertLess(patched.index('"_arm64e",'), patched.index('"_arm64",'))
        self.assertEqual(v81.patch(patched), patched)
        self.assertEqual(patched.replace(v81.PATCHED,v81.ORIGINAL),source)

    def test_fails_closed_on_drift_duplicate_or_misplacement(self):
        with self.assertRaises(ValueError):
            v81.patch("unknown upstream implementation")
        with self.assertRaises(ValueError):
            v81.patch(v81.ORIGINAL * 2)
        with self.assertRaises(ValueError):
            v81.patch(v81.ORIGINAL + v81.MARKER)
        with self.assertRaises(ValueError):
            v81.patch(v81.PATCHED.replace('"_arm64e_x1",', '"_arm64e_x1",\n\t\t\t"_arm64e_x1",'))
        with self.assertRaises(ValueError):
            v81.patch(v81.PATCHED.replace('"_arm64e_x1",', '"_arm64e_x1",') + v81.MARKER)

    def test_mutates_only_pinned_litehook_source_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / v81.RELATIVE
            target.parent.mkdir(parents=True)
            target.write_text(v81.ORIGINAL)
            v81.apply(root)
            self.assertEqual(target.read_text(),v81.PATCHED)
            v81.apply(root)
            self.assertEqual(target.read_text(),v81.PATCHED)
            self.assertEqual(set(f.relative_to(root).as_posix() for f in root.rglob("*") if f.is_file()),
                             {"litehook/src/litehook.c"})

if __name__ == "__main__":
    unittest.main()
