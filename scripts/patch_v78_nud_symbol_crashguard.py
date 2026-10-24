#!/usr/bin/env python3
"""V78: fail-safe CoreFoundation preference-symbol initialization on iOS 27.2.

The 2026-10-24 LiveProcess crash is EXC_BAD_ACCESS at address zero in
NUDGuestHooksInit (+456), ~60 ms after process launch. Pinned upstream
NSUserDefaults.m dereferences two optional private symbol lookup results
without verifying they were found. Preserve all guest preference mechanisms
when symbols exist; when a symbol is absent, skip ONLY that private cache
override rather than crash the entire LiveProcess extension.
"""
from pathlib import Path
import sys

TARGET = Path("LiveContainer/Tweaks/NSUserDefaults.m")
MARKER = "SCARLET_V78_NUD_NULL_SYMBOL_GUARD"

OLD_APP_CACHE = """    CFStringRef* _CFPrefsCurrentAppIdentifierCache = getCachedSymbol(@"__CFPrefsCurrentAppIdentifierCache", coreFoundationHeader);
    if(!_CFPrefsCurrentAppIdentifierCache) {
        _CFPrefsCurrentAppIdentifierCache = litehook_find_dsc_symbol(coreFoundationPath, "__CFPrefsCurrentAppIdentifierCache");
        uint64_t offset = (uint64_t)((void*)_CFPrefsCurrentAppIdentifierCache - (void*)coreFoundationHeader);
        saveCachedSymbol(@"__CFPrefsCurrentAppIdentifierCache", coreFoundationHeader, offset);
    }
    [NSUserDefaults.lcUserDefaults _setIdentifier:(__bridge NSString*)CFStringCreateCopy(nil, *_CFPrefsCurrentAppIdentifierCache)];
    *_CFPrefsCurrentAppIdentifierCache = (__bridge CFStringRef)NSUserDefaults.lcGuestAppId;"""

DSC_DIAG_HELPER = """static void ScarletV78LogDSCReadability(NSString* hookPath) {
    // Diagnostic only: cache discovery/readability is not proof of symbol absence.
    // Avoid extra costly litehook_find_dsc_symbol calls on the guest startup path.
    const char* locatedDSC = litehook_locate_dsc();
    NSString* cachePath = locatedDSC != NULL && locatedDSC[0] != '\\0'
        ? [NSString stringWithUTF8String:locatedDSC] : nil;
    NSString* symbolsPath = [cachePath stringByAppendingString:@".symbols"];
    NSFileManager* manager = NSFileManager.defaultManager;
    NSLog(@"[SCARLET_V78_DIAG] hook_path=%@ dsc_located=%@ dsc_main_readable=%@ dsc_symbols_readable=%@",
          hookPath,
          cachePath != nil ? @"yes" : @"no",
          cachePath != nil && [manager isReadableFileAtPath:cachePath] ? @"yes" : @"no",
          symbolsPath != nil && [manager isReadableFileAtPath:symbolsPath] ? @"yes" : @"no");
}

"""

NEW_APP_CACHE = """    // SCARLET_V78_NUD_NULL_SYMBOL_GUARD: private symbols may be absent on iOS 27.2.
    // Do not cache an invalid address or dereference a NULL symbol pointer.
    CFStringRef* _CFPrefsCurrentAppIdentifierCache = NULL;
    NSString* prefsCacheResult = @"not_attempted";
    NSString* prefsDscResult = @"not_attempted";
    if (coreFoundationHeader != NULL) {
        _CFPrefsCurrentAppIdentifierCache = getCachedSymbol(@"__CFPrefsCurrentAppIdentifierCache", coreFoundationHeader);
        prefsCacheResult = _CFPrefsCurrentAppIdentifierCache != NULL ? @"hit" : @"miss";
        if (_CFPrefsCurrentAppIdentifierCache == NULL) {
            _CFPrefsCurrentAppIdentifierCache = litehook_find_dsc_symbol(coreFoundationPath, "__CFPrefsCurrentAppIdentifierCache");
            prefsDscResult = _CFPrefsCurrentAppIdentifierCache != NULL ? @"hit" : @"miss";
            if (_CFPrefsCurrentAppIdentifierCache == NULL) {
                ScarletV78LogDSCReadability(@"prefs_first");
            }
            if (_CFPrefsCurrentAppIdentifierCache != NULL) {
                uint64_t offset = (uint64_t)((void*)_CFPrefsCurrentAppIdentifierCache - (void*)coreFoundationHeader);
                saveCachedSymbol(@"__CFPrefsCurrentAppIdentifierCache", coreFoundationHeader, offset);
            }
        }
    }
    NSLog(@"[SCARLET_V78_DIAG] hook_path=prefs_first prefs_cache=%@ prefs_dsc=%@ prefs_symbol=%@",
          prefsCacheResult, prefsDscResult,
          _CFPrefsCurrentAppIdentifierCache != NULL ? @"present" : @"missing");
    if (_CFPrefsCurrentAppIdentifierCache != NULL) {
        CFStringRef previousHostIdentifier = *_CFPrefsCurrentAppIdentifierCache;
        // Diagnostic is intentionally non-address-bearing: no ASLR pointers in logs.
        NSLog(@"[SCARLET_V78_DIAG] prefs_symbol=present prefs_value=%@",
              previousHostIdentifier != NULL ? @"non_null" : @"null");
        if (previousHostIdentifier != NULL) {
            CFStringRef identifierCopy = CFStringCreateCopy(kCFAllocatorDefault, previousHostIdentifier);
            if (identifierCopy != NULL) {
                [NSUserDefaults.lcUserDefaults _setIdentifier:(__bridge_transfer NSString*)identifierCopy];
            }
        } else {
            NSLog(@"[SCARLET_V78] preference_cache_value_null; host identifier left unchanged");
        }
        *_CFPrefsCurrentAppIdentifierCache = (__bridge CFStringRef)NSUserDefaults.lcGuestAppId;
        NSLog(@"[SCARLET_V78_DIAG] prefs_override=applied");
    } else {
        NSLog(@"[SCARLET_V78_DIAG] prefs_symbol=missing prefs_override=skipped");
        NSLog(@"[SCARLET_V78] preference_cache_symbol_missing; skipped unsafe private override");
    }"""

OLD_LANGUAGE_CACHE = """        CFMutableArrayRef* _CFBundleUserLanguages = getCachedSymbol(@"__CFBundleUserLanguages", coreFoundationHeader);
        if(!_CFBundleUserLanguages) {
            _CFBundleUserLanguages = litehook_find_dsc_symbol(coreFoundationPath, "__CFBundleUserLanguages");
            uint64_t offset = (uint64_t)((void*)_CFBundleUserLanguages - (void*)coreFoundationHeader);
            saveCachedSymbol(@"__CFBundleUserLanguages", coreFoundationHeader, offset);
        }
        // set _CFBundleUserLanguages to selected languages
        NSMutableArray* newUserLanguages = [NSMutableArray arrayWithObjects:selectedLanguage, nil];
        *_CFBundleUserLanguages = (__bridge CFMutableArrayRef)newUserLanguages;"""

NEW_LANGUAGE_CACHE = """        CFMutableArrayRef* _CFBundleUserLanguages = NULL;
        NSString* langCacheResult = @"not_attempted";
        NSString* langDscResult = @"not_attempted";
        if (coreFoundationHeader != NULL) {
            _CFBundleUserLanguages = getCachedSymbol(@"__CFBundleUserLanguages", coreFoundationHeader);
            langCacheResult = _CFBundleUserLanguages != NULL ? @"hit" : @"miss";
            if (_CFBundleUserLanguages == NULL) {
                _CFBundleUserLanguages = litehook_find_dsc_symbol(coreFoundationPath, "__CFBundleUserLanguages");
                langDscResult = _CFBundleUserLanguages != NULL ? @"hit" : @"miss";
                if (_CFBundleUserLanguages == NULL) {
                    ScarletV78LogDSCReadability(@"lang_second");
                }
                if (_CFBundleUserLanguages != NULL) {
                    uint64_t offset = (uint64_t)((void*)_CFBundleUserLanguages - (void*)coreFoundationHeader);
                    saveCachedSymbol(@"__CFBundleUserLanguages", coreFoundationHeader, offset);
                }
            }
        }
        // AppleLanguages still gets stored in newStandardUserDefaults above.
        NSLog(@"[SCARLET_V78_DIAG] hook_path=lang_second lang_cache=%@ lang_dsc=%@ lang_symbol=%@",
              langCacheResult, langDscResult,
              _CFBundleUserLanguages != NULL ? @"present" : @"missing");
        if (_CFBundleUserLanguages != NULL) {
            CFMutableArrayRef previousUserLanguages = *_CFBundleUserLanguages;
            NSLog(@"[SCARLET_V78_DIAG] lang_value=%@",
                  previousUserLanguages != NULL ? @"non_null" : @"null");
            NSMutableArray* newUserLanguages = [NSMutableArray arrayWithObjects:selectedLanguage, nil];
            *_CFBundleUserLanguages = (__bridge CFMutableArrayRef)newUserLanguages;
            NSLog(@"[SCARLET_V78_DIAG] lang_override=applied");
        } else {
            NSLog(@"[SCARLET_V78_DIAG] lang_value=not_read lang_override=skipped");
            NSLog(@"[SCARLET_V78] language_cache_symbol_missing; preserved AppleLanguages override");
        }"""


OLD_UNSELECTED_LANGUAGE = """    } else {
        [newStandardUserDefaults removeObjectForKey:@"AppleLanguages"];
    }"""

NEW_UNSELECTED_LANGUAGE = """    } else {
        // No language override requested. Do not mistake 'not_attempted' for symbol missing.
        NSLog(@"[SCARLET_V78_DIAG] hook_path=lang_second lang_skip=no_selected_language lang_cache=not_attempted lang_dsc=not_attempted lang_symbol=not_attempted lang_value=not_read lang_override=not_attempted");
        [newStandardUserDefaults removeObjectForKey:@"AppleLanguages"];
    }"""


# V78 Gate 3: prove the selector exchange occurred, and classify non-Apple
# preference routing without logging identifiers or flooding runtime logs.
OLD_CF_PREFS_SWIZZLE = """    swizzle2(CFPrefsPlistSourceClass, @selector(initWithDomain:user:byHost:containerPath:containingPreferences:), CFPrefsPlistSource2.class, @selector(hook_initWithDomain:user:byHost:containerPath:containingPreferences:));"""

NEW_CF_PREFS_SWIZZLE = """    // SCARLET_V78_CF_PREFS_SWIZZLE_VERIFY: verify *pre-exchange* IMP identity.
    // Comparing to the hook selector after exchange can inspect the original IMP.
    SEL originalPrefsSelector = @selector(initWithDomain:user:byHost:containerPath:containingPreferences:);
    SEL hookedPrefsSelector = @selector(hook_initWithDomain:user:byHost:containerPath:containingPreferences:);
    Method sourceHookMethod = class_getInstanceMethod(CFPrefsPlistSource2.class, hookedPrefsSelector);
    Method originalPrefsMethod = CFPrefsPlistSourceClass != Nil
        ? class_getInstanceMethod(CFPrefsPlistSourceClass, originalPrefsSelector) : NULL;
    IMP expectedHookIMP = sourceHookMethod != NULL ? method_getImplementation(sourceHookMethod) : NULL;
    IMP originalPrefsIMP = originalPrefsMethod != NULL ? method_getImplementation(originalPrefsMethod) : NULL;
    if (sourceHookMethod != NULL && originalPrefsMethod != NULL) {
        // If hook was installed previously, do not swap it back out.
        if (originalPrefsIMP != expectedHookIMP) {
            swizzle2(CFPrefsPlistSourceClass, originalPrefsSelector,
                     CFPrefsPlistSource2.class, hookedPrefsSelector);
        }
    }
    Method installedPrefsMethod = CFPrefsPlistSourceClass != Nil
        ? class_getInstanceMethod(CFPrefsPlistSourceClass, originalPrefsSelector) : NULL;
    Method forwardedPrefsMethod = CFPrefsPlistSourceClass != Nil
        ? class_getInstanceMethod(CFPrefsPlistSourceClass, hookedPrefsSelector) : NULL;
    BOOL prefsSwizzleInstalled = expectedHookIMP != NULL && installedPrefsMethod != NULL
        && method_getImplementation(installedPrefsMethod) == expectedHookIMP
        && forwardedPrefsMethod != NULL;
    NSLog(@"[SCARLET_V78_DIAG] cfprefs_swizzle=%@ original_selector=%@ hook_selector=%@",
          prefsSwizzleInstalled ? @"installed" : @"failed",
          originalPrefsMethod != NULL ? @"present" : @"missing",
          sourceHookMethod != NULL ? @"present" : @"missing");"""

OLD_CF_PREFS_ROUTE = """@implementation CFPrefsPlistSource2
-(id)hook_initWithDomain:(CFStringRef)domain user:(CFStringRef)user byHost:(bool)host containerPath:(CFStringRef)containerPath containingPreferences:(id)arg5 {
    if(isAppleIdentifier((__bridge NSString*)domain)) {"""

NEW_CF_PREFS_ROUTE = """// One log per classification per process; do not record preference domains,
// usernames, app identifiers, paths, values, memory addresses, or key names.
static atomic_uint_fast32_t scarletV78RouteSeen = ATOMIC_VAR_INIT(0);
static void ScarletV78LogCFPrefsRoute(CFStringRef domain, CFStringRef user, bool byHost) {
    const BOOL appleDomain = isAppleIdentifier((__bridge NSString*)domain);
    const BOOL anyUser = user == kCFPreferencesAnyUser;
    const BOOL currentUser = user == kCFPreferencesCurrentUser;
    const unsigned int userClass = anyUser ? 0u : (currentUser ? 1u : 2u);
    const unsigned int index = (appleDomain ? 6u : 0u) + userClass * 2u + (byHost ? 1u : 0u);
    const uint_fast32_t flag = ((uint_fast32_t)1u << index);
    if ((atomic_fetch_or_explicit(&scarletV78RouteSeen, flag, memory_order_relaxed) & flag) != 0) return;
    NSLog(@"[SCARLET_V78_DIAG] cfprefs_domain=%@ cfprefs_user=%@ cfprefs_by_host=%@ cfprefs_route=%@",
          appleDomain ? @"apple" : @"non_apple",
          anyUser ? @"any_user" : (currentUser ? @"current_user" : @"other_user"),
          byHost ? @"true" : @"false",
          appleDomain ? @"original_path" : (anyUser ? @"guest_path_any_to_current_user" : @"guest_path"));
}

@implementation CFPrefsPlistSource2
-(id)hook_initWithDomain:(CFStringRef)domain user:(CFStringRef)user byHost:(bool)host containerPath:(CFStringRef)containerPath containingPreferences:(id)arg5 {
    ScarletV78LogCFPrefsRoute(domain, user, host);
    if(isAppleIdentifier((__bridge NSString*)domain)) {"""

OLD_ATOMIC_IMPORT = "#include \"Tweaks.h\""
NEW_ATOMIC_IMPORT = "#include \"Tweaks.h\"\\n#include <stdatomic.h>"

def patch(source: str) -> str:
    if MARKER in source:
        if (source.count(MARKER) != 1 or source.count("SCARLET_V78_CF_PREFS_SWIZZLE_VERIFY") != 1
            or source.count("preference_cache_symbol_missing") != 1
            or source.count("language_cache_symbol_missing") != 1):
            raise ValueError("V78 partial or duplicated crash guard")
        return source
    for original, label in (
        (OLD_APP_CACHE, "application"),
        (OLD_LANGUAGE_CACHE, "language"),
        (OLD_UNSELECTED_LANGUAGE, "unselected-language"),
        (OLD_CF_PREFS_SWIZZLE, "cfprefs swizzle"),
        (OLD_CF_PREFS_ROUTE, "cfprefs route"),
        (OLD_ATOMIC_IMPORT, "atomic include"),
    ):
        if source.count(original) != 1:
            raise ValueError(f"V78 pinned {label} preference block missing or duplicated")
    if source.count("void NUDGuestHooksInit(void) {") != 1:
        raise ValueError("V78 pinned NUDGuestHooksInit entry missing or duplicated")
    return (
        source.replace("void NUDGuestHooksInit(void) {", DSC_DIAG_HELPER + "void NUDGuestHooksInit(void) {", 1)
        .replace(OLD_ATOMIC_IMPORT, NEW_ATOMIC_IMPORT, 1)
        .replace(OLD_CF_PREFS_SWIZZLE, NEW_CF_PREFS_SWIZZLE, 1)
        .replace(OLD_CF_PREFS_ROUTE, NEW_CF_PREFS_ROUTE, 1)
        .replace(OLD_APP_CACHE, NEW_APP_CACHE, 1)
        .replace(OLD_LANGUAGE_CACHE, NEW_LANGUAGE_CACHE, 1)
        .replace(OLD_UNSELECTED_LANGUAGE, NEW_UNSELECTED_LANGUAGE, 1)
    )

def apply(root: Path) -> None:
    target = root / TARGET
    original = target.read_text(encoding="utf-8")
    updated = patch(original)
    if patch(updated) != updated:
        raise ValueError("V78 idempotency failed")
    if updated != original:
        target.write_text(updated, encoding="utf-8")
    print("[PASS] V78 LiveProcess NUD private CoreFoundation cache NULL crash guard")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v78_nud_symbol_crashguard.py <LiveContainer source root>")
    apply(Path(sys.argv[1]))
