"""V79 iOS 27.2 LiveProcess dlopen_nolock+596 null-vtable regression."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "patch_v79_dyld_vtable_crashguard",
    ROOT / "scripts" / "patch_v79_dyld_vtable_crashguard.py",
)
v79 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v79)


class DyldVtableNullGuardTests(unittest.TestCase):
    @staticmethod
    def fixture():
        return "\n".join(original for original, _ in v79.REPLACEMENTS) + "\n"

    def test_exact_anchors_and_replay(self):
        before = self.fixture()
        after = v79.patch(before)
        self.assertEqual(after.count(v79.MARKER), 1)
        self.assertEqual(v79.patch(after), after)
        self.assertEqual(len(v79.REPLACEMENTS), 5)
        self.assertNotIn('NSCAssert(lockOffset != -1', after)
        self.assertNotIn('NSCAssert(unlockOffset != -1', after)
        for old, new in v79.REPLACEMENTS:
            self.assertIn(new, after)
            if old not in new:
                self.assertNotIn(old, after)

    def test_fail_closed_null_vtable_symbol_and_cache(self):
        after = v79.patch(self.fixture())
        self.assertIn('if (vtable == NULL || func == NULL) return -1;', after)
        self.assertIn('if (vtableLibSystemHelpers == NULL)', after)
        self.assertIn('if (lockPtr == NULL || unlockPtr == NULL)', after)
        self.assertIn('safe_abort=missing_mandatory_vtable', after)
        self.assertIn('safe_abort=lock_symbol_or_vtable_missing', after)
        self.assertIn('safe_abort=unlock_symbol_or_vtable_missing', after)
        self.assertIn('safe_abort=missing_lock_pointer', after)
        self.assertIn('safe_abort=missing_lock_implementation', after)
        self.assertIn('if (*lockPtr == NULL || *unlockPtr == NULL ||', after)
        self.assertIn('shouldPatchTrylock = false;', after)
        self.assertNotIn('return dlopen(path, mode)', after)
        self.assertNotIn('return orig_dlopen(path, mode)', after)
        self.assertNotIn('vtableLibSystemHelpers + (-1)', after)

    def test_rejects_source_drift_and_partial_patch(self):
        source = self.fixture()
        for original, _ in v79.REPLACEMENTS:
            with self.subTest(anchor=original[:38]):
                with self.assertRaises(ValueError):
                    v79.patch(source.replace(original, original[:-1] + "#", 1))
        patched = v79.patch(source)
        with self.assertRaises(ValueError):
            v79.patch(patched.replace('safe_abort=missing_mandatory_vtable', 'missing_marker', 1))
        with self.assertRaises(ValueError):
            v79.patch(patched + "\n" + v79.MARKER)

    def test_inlined_search_vtable_null_behavior_native(self):
        compiler = shutil.which("cc") or shutil.which("clang")
        if compiler is None:
            # Source checks still run on the host without a native C toolchain.
            return
        # Isolate ONLY the pinned searchVtable replacement, not the
        # concatenated multi-anchor fixture containing Objective-C helpers.
        # The previous extraction accidentally swallowed the subsequent
        # dlopen_nolock body on macOS and made a pure-C test uncompilable.
        actual = v79.patch(self.fixture())
        search_header = v79.REPLACEMENTS[0][1]
        self.assertIn(search_header, actual)
        c = (
            "#include <stddef.h>\n"
            + search_header
            + "\n        if (vtable[i] == func) return i;\n"
            + "    }\n"
            + "    return -1;\n"
            + "}\n"
            "int main(void) {\n"
            "    void* table[100] = { 0 };\n"
            "    table[13] = (void*)0x1234;\n"
            "    if (searchVtable(NULL, table[13]) != -1) return 10;\n"
            "    if (searchVtable(table, NULL) != -1) return 11;\n"
            "    if (searchVtable(table, (void*)0x1234) != 13) return 12;\n"
            "    if (searchVtable(table, (void*)0x5678) != -1) return 13;\n"
            "    return 0;\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search_vtable.c"
            binary = Path(tmp) / "search_vtable"
            path.write_text(c)
            built = subprocess.run([compiler, str(path), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_full_pinned_source_if_available(self):
        source_dir = os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        if not source_dir:
            return
        target = Path(source_dir) / v79.TARGET
        original = target.read_text(encoding="utf-8")
        already_patched = os.environ.get("V79_PATCHED_LIVECONTAINER") == "1"
        if already_patched:
            self.assertEqual(v79.patch(original), original)
        else:
            self.assertNotEqual(v79.patch(original), original)


if __name__ == "__main__":
    unittest.main()
