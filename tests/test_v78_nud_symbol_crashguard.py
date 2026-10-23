"""V78 regression tests: iOS 27.2 LiveProcess NUDGuestHooksInit crash guard."""
from pathlib import Path
import importlib.util
import os
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "patch_v78_nud_symbol_crashguard",
    HERE / "scripts" / "patch_v78_nud_symbol_crashguard.py",
)
v78 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v78)

class NUDGuestHooksCrashGuardTests(unittest.TestCase):
    def fixture(self):
        # The blocks must match pinned source exactly. Everything unrelated is
        # preserved, including registration, JIT, refresh, UI and extensions.
        return "\n".join([
            "void NUDGuestHooksInit(void) {",
            '    const char* coreFoundationPath = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation";',
            "    mach_header_u* coreFoundationHeader = LCGetLoadedImageHeader(2, coreFoundationPath);",
            v78.OLD_APP_CACHE,
            '    NSString* selectedLanguage = NSUserDefaults.guestAppInfo[@"LCSelectedLanguage"];',
            "    if(selectedLanguage) {",
            '        [newStandardUserDefaults setObject:@[selectedLanguage] forKey:@"AppleLanguages"];',
            v78.OLD_LANGUAGE_CACHE,
            "    }",
            "}",
        ]) + "\n"

    def test_both_null_symbol_paths_are_guarded(self):
        result = v78.patch(self.fixture())
        self.assertEqual(result.count(v78.MARKER), 1)
        self.assertIn("if (_CFPrefsCurrentAppIdentifierCache != NULL)", result)
        self.assertIn("if (_CFBundleUserLanguages != NULL)", result)
        self.assertIn("if (coreFoundationHeader != NULL)", result)
        self.assertIn("if (identifierCopy != NULL)", result)
        self.assertIn('preference_cache_symbol_missing', result)
        self.assertIn('language_cache_symbol_missing', result)
        self.assertIn('setObject:@[selectedLanguage] forKey:@"AppleLanguages"', result)
        self.assertNotIn(v78.OLD_APP_CACHE, result)
        self.assertNotIn(v78.OLD_LANGUAGE_CACHE, result)

    def assert_safe_pref_chain(self, source):
        # This is a SOURCE contract test, not proof of arm64 runtime behavior.
        self.assertRegex(
            source,
            r"if \(_CFPrefsCurrentAppIdentifierCache != NULL\) \{\s+CFStringRef previousHostIdentifier = \*_CFPrefsCurrentAppIdentifierCache;",
        )
        self.assertRegex(
            source,
            r"if \(previousHostIdentifier != NULL\) \{\s+CFStringRef identifierCopy = CFStringCreateCopy",
        )
        self.assertRegex(
            source,
            r"if \(_CFBundleUserLanguages != NULL\) \{[\s\S]*?\*_CFBundleUserLanguages =",
        )

    def test_second_level_null_guard_and_diagnostic_branches(self):
        source = v78.patch(self.fixture())
        self.assert_safe_pref_chain(source)
        for event in (
            "prefs_symbol=present prefs_value=%@",
            "prefs_symbol=missing prefs_override=skipped",
            "prefs_override=applied",
            "language_symbol=present language_override=applied",
            "language_symbol=missing language_override=skipped",
        ):
            self.assertIn(event, source)
        # Diagnostics must not leak process ASLR addresses.
        self.assertNotIn("prefs_symbol=%p", source)
        self.assertNotIn("language_symbol=%p", source)

    def test_mutated_null_guards_are_detected(self):
        patched = v78.patch(self.fixture())
        # Mutant A: permit dereference of NULL exported symbol.
        mutant_a = patched.replace(
            "if (_CFPrefsCurrentAppIdentifierCache != NULL) {",
            "if (YES) {", 1,
        )
        with self.assertRaises(AssertionError):
            self.assert_safe_pref_chain(mutant_a)
        # Mutant B: permit CFStringCreateCopy with a NULL first-level value.
        mutant_b = patched.replace(
            "if (previousHostIdentifier != NULL) {",
            "if (YES) {", 1,
        )
        with self.assertRaises(AssertionError):
            self.assert_safe_pref_chain(mutant_b)
        # Mutant C: permit writing through an absent language symbol.
        mutant_c = patched.replace(
            "if (_CFBundleUserLanguages != NULL) {",
            "if (YES) {", 1,
        )
        with self.assertRaises(AssertionError):
            self.assert_safe_pref_chain(mutant_c)

    def test_idempotent_and_unrelated_code_unchanged(self):
        original = self.fixture()
        once = v78.patch(original)
        self.assertEqual(once, v78.patch(once))
        self.assertIn("void NUDGuestHooksInit(void)", once)
        self.assertIn("LCSelectedLanguage", once)

    def test_fail_closed_on_wrong_revision_or_partial_patch(self):
        with self.assertRaisesRegex(ValueError, "block"):
            v78.patch("unrelated upstream")
        with self.assertRaisesRegex(ValueError, "partial"):
            v78.patch(v78.MARKER)

    def test_applies_idempotently_to_fixture_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / v78.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(self.fixture(), encoding="utf-8")
            v78.apply(root)
            once = path.read_text(encoding="utf-8")
            v78.apply(root)
            self.assertEqual(once, path.read_text(encoding="utf-8"))

    def test_generated_source_after_ci_patching(self):
        root = os.getenv("LIVE_CONTAINER_TEST_SOURCE")
        if not root or os.getenv("V78_PATCHED_LIVECONTAINER") != "1":
            return
        text = (Path(root) / v78.TARGET).read_text(encoding="utf-8")
        self.assertEqual(v78.patch(text), text)
        self.assertEqual(text.count(v78.MARKER), 1)
        self.assertIn("preference_cache_symbol_missing", text)

if __name__ == "__main__":
    unittest.main()
