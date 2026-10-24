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
            '    NSUserDefaults* newStandardUserDefaults = [[NSUserDefaults alloc] initWithSuiteName:@"whatever"];',
            '    [newStandardUserDefaults _setIdentifier:NSUserDefaults.lcGuestAppId];',
            '    NSUserDefaults.standardUserDefaults = newStandardUserDefaults;',
            '    NSString* selectedLanguage = NSUserDefaults.guestAppInfo[@"LCSelectedLanguage"];',
            "    if(selectedLanguage) {",
            '        [newStandardUserDefaults setObject:@[selectedLanguage] forKey:@"AppleLanguages"];',
            v78.OLD_LANGUAGE_CACHE,
            "    } else {",
            '        [newStandardUserDefaults removeObjectForKey:@"AppleLanguages"];',
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
        self.assertIn("lang_symbol=not_attempted", result)
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
            r"if \(_CFBundleUserLanguages != NULL\) \{\s+CFMutableArrayRef previousUserLanguages = \*_CFBundleUserLanguages;",
        )

    def test_second_level_null_guard_and_diagnostic_branches(self):
        source = v78.patch(self.fixture())
        self.assert_safe_pref_chain(source)
        for event in (
            "prefs_cache=%@ prefs_dsc=%@ prefs_symbol=%@",
            "prefs_symbol=present prefs_value=%@",
            "prefs_symbol=missing prefs_override=skipped",
            "prefs_override=applied",
            "lang_cache=%@ lang_dsc=%@ lang_symbol=%@",
            "lang_value=%@",
            "lang_override=applied",
            "lang_value=not_read lang_override=skipped",
            "lang_symbol=not_attempted lang_value=not_read lang_override=not_attempted",
        ):
            self.assertIn(event, source)
        # Diagnostics must not leak process ASLR addresses.
        self.assertNotIn("prefs_symbol=%p", source)
        self.assertNotIn("language_symbol=%p", source)
        self.assertNotIn("lang_symbol=%p", source)
        self.assertNotIn("prefs_cache=%p", source)
        self.assertNotIn("lang_cache=%p", source)

    def test_lookup_attribution_is_before_dereference(self):
        source = v78.patch(self.fixture())
        # Each source reports the result of the actual lookup it performs.
        self.assertLess(
            source.index('prefsCacheResult = _CFPrefsCurrentAppIdentifierCache != NULL ? @"hit" : @"miss";'),
            source.index('if (_CFPrefsCurrentAppIdentifierCache == NULL) {'),
        )
        self.assertLess(
            source.index('prefsDscResult = _CFPrefsCurrentAppIdentifierCache != NULL ? @"hit" : @"miss";'),
            source.index('saveCachedSymbol(@"__CFPrefsCurrentAppIdentifierCache"'),
        )
        self.assertLess(
            source.index('langDscResult = _CFBundleUserLanguages != NULL ? @"hit" : @"miss";'),
            source.index('saveCachedSymbol(@"__CFBundleUserLanguages"'),
        )
        self.assertIn('prefsCacheResult = @"not_attempted";', source)
        self.assertIn('langDscResult = @"not_attempted";', source)

    def test_cache_miss_only_skips_private_override_not_guest_defaults(self):
        src = v78.patch(self.fixture())
        self.assertLess(
            src.index('preference_cache_symbol_missing; skipped unsafe private override'),
            src.index('NSUserDefaults.standardUserDefaults = newStandardUserDefaults;'),
        )
        self.assertLess(
            src.index('NSUserDefaults.standardUserDefaults = newStandardUserDefaults;'),
            src.index('NSString* selectedLanguage = NSUserDefaults.guestAppInfo'),
        )
        self.assertNotIn('return;', src[src.index('preference_cache_symbol_missing'):src.index('NSUserDefaults.standardUserDefaults = newStandardUserDefaults;')])

    def test_readonly_dsc_probe_only_on_lookup_failure(self):
        src = v78.patch(self.fixture())
        self.assertEqual(src.count("static void ScarletV78LogDSCReadability"), 1)
        self.assertIn('dsc_main_readable=%@ dsc_symbols_readable=%@', src)
        self.assertIn('isReadableFileAtPath:cachePath', src)
        self.assertIn('isReadableFileAtPath:symbolsPath', src)
        self.assertNotIn('dlsym(', src)
        self.assertEqual(src.count('= litehook_find_dsc_symbol('), 2)
        self.assertIn('hook_path=prefs_first prefs_cache=%@', src)
        self.assertIn('hook_path=lang_second lang_cache=%@', src)
        self.assertIn('hook_path=lang_second lang_skip=no_selected_language', src)
        self.assertRegex(src, r'if \(_CFPrefsCurrentAppIdentifierCache == NULL\) \{\s+ScarletV78LogDSCReadability\(@"prefs_first"\);')
        self.assertRegex(src, r'if \(_CFBundleUserLanguages == NULL\) \{\s+ScarletV78LogDSCReadability\(@"lang_second"\);')
        self.assertLess(src.index('ScarletV78LogDSCReadability(@"prefs_first")'), src.index('prefs_cache=%@'))

    def test_unselected_language_path_is_explicit(self):
        result = v78.patch(self.fixture())
        self.assertEqual(result.count("lang_symbol=not_attempted"), 1)
        self.assertIn('removeObjectForKey:@"AppleLanguages"', result)
        self.assertNotIn(v78.OLD_UNSELECTED_LANGUAGE, result)

    def test_mutated_null_guards_are_detected(self):
        patched = v78.patch(self.fixture())
        # Mutant A: permit dereference of NULL exported symbol.
        mutant_a = patched.replace(
            "    if (_CFPrefsCurrentAppIdentifierCache != NULL) {\\n        CFStringRef previousHostIdentifier".replace("\\n", "\n"),
            "    if (YES) {\\n        CFStringRef previousHostIdentifier".replace("\\n", "\n"), 1,
        )
        self.assertNotEqual(patched, mutant_a)
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
            "        if (_CFBundleUserLanguages != NULL) {\\n            CFMutableArrayRef previousUserLanguages".replace("\\n", "\n"),
            "        if (YES) {\\n            CFMutableArrayRef previousUserLanguages".replace("\\n", "\n"), 1,
        )
        self.assertNotEqual(patched, mutant_c)
        with self.assertRaises(AssertionError):
            self.assert_safe_pref_chain(mutant_c)

    def test_null_symbol_offsets_are_never_cached(self):
        # The UUID-matched V77 original did save a NULL-derived offset
        # after litehook_find_dsc_symbol returned NULL, before LDR [X20].
        # Both prefs and language symbol-save paths must guard the write.
        for symbol, label in (
            ("_CFPrefsCurrentAppIdentifierCache", "prefs"),
            ("_CFBundleUserLanguages", "language"),
        ):
            result = v78.patch(self.fixture())
            guard = f"if ({symbol} != NULL) {{"
            save = f'saveCachedSymbol(@"__CFPrefsCurrentAppIdentifierCache"' if label == "prefs" else f'saveCachedSymbol(@"__CFBundleUserLanguages"'
            before_save = result.split(save, 1)[0]
            self.assertIn(guard, before_save)
            anchor = guard + "\\n" + (
                "                uint64_t offset" if label == "prefs"
                else "                    uint64_t offset"
            )
            anchor = anchor.replace("\\n", "\n")
            self.assertEqual(before_save.count(anchor), 1)
            mutated = result.replace(anchor, anchor.replace(guard, "if (YES) {"), 1)
            self.assertNotEqual(mutated, result)
            self.assertNotIn(anchor, mutated.split(save, 1)[0])

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

    def test_real_source_preserves_cfpreferences_path_isolation_hook(self):
        # Source-level invariant only: runtime CFPreferences isolation remains
        # an explicit iPhone Gate 3. Validate the *full* pinned generated file.
        root = os.getenv("LIVE_CONTAINER_TEST_SOURCE")
        if not root or os.getenv("V78_PATCHED_LIVECONTAINER") != "1":
            return
        src = (Path(root) / v78.TARGET).read_text(encoding="utf-8")
        self.assertIn("Class CFPrefsPlistSourceClass = NSClassFromString(@\"CFPrefsPlistSource\");", src)
        self.assertIn("swizzle2(CFPrefsPlistSourceClass,", src)
        self.assertIn("@selector(hook_initWithDomain:user:byHost:containerPath:containingPreferences:)", src)
        self.assertIn("if(isAppleIdentifier((__bridge NSString*)domain))", src)
        self.assertIn("containerPath:(__bridge CFStringRef)appContainerPath", src)
        self.assertIn("NSUserDefaults.standardUserDefaults = newStandardUserDefaults;", src)
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
