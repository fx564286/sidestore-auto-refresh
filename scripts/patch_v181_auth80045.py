#!/usr/bin/env python3
"""Forward-port -80045 compatible Apple sign-in identity to current SideSign.

Keeps user-configured Anisette client info, explicit UA overrides, Apple
2FA flow, ADI, Keychain, saved pairing, signing certificates and account data.
No synthetic retries or changes to Apple request signing.
"""
from pathlib import Path
import argparse

SIDESIGN = Path("Dependencies/SideSign/Sources/DeveloperPortal/Authentication.swift")
HANDLER = Path("SideStore/Handlers/SignInFlowHandler.swift")
MARK = "SCARLET_V181_80045_PROFILE"

HELPER = r"""
// SCARLET_V181_80045_PROFILE: only adapt the *default* macOS/Xcode agent
// when the user has explicitly selected Windows/Android Anisette client info.
// A configured custom SideSign user agent always wins. No automatic identity
// override, ADI reset, credential replay or SRP retry is performed.
private func scarletV181CompatibleUserAgent(clientInfo: String, fallback: String,
                                           defaultAgent: String) -> String {
    let compatibleProfile = clientInfo.contains("<Windows;") || clientInfo.contains("<Android;")
    if compatibleProfile && fallback == defaultAgent {
        return "akd/1.0 CFNetwork/808.1.4"
    }
    return fallback
}
"""
OLD_GSA = '            "User-Agent": h.grandSlam.userAgent,'
NEW_GSA = ('            "User-Agent": scarletV181CompatibleUserAgent('
           'clientInfo: anisetteData.clientInfo, fallback: h.grandSlam.userAgent,'
           ' defaultAgent: Constants.GrandSlam.userAgent),')
OLD_2FA = '            "User-Agent": h.developerServices.userAgent,'
NEW_2FA = ('            "User-Agent": scarletV181CompatibleUserAgent('
           'clientInfo: a.clientInfo, fallback: h.developerServices.userAgent,'
           ' defaultAgent: Constants.DeveloperServices.userAgent),')

OLD_HANDLER = """            case .failure(let error):
                completionHandler(.failure(error))
"""
NEW_HANDLER = """            case .failure(let error):
                // SCARLET_V181_80045_PROFILE: Apple GrandSlam rejected the
                // selected client profile; this is not a pairing/password
                // verdict. Never erase credentials or retry automatically.
                if case ServerError.underlyingError(let code, _) = error, code == -80045 {
                    let detail = NSLocalizedString(
                        "Apple authentication rejected the current Anisette client profile (-80045). " +
                        "Open Settings > User Customizations > Anisette Client Configuration. " +
                        "Choose a compatible client profile and Anisette server; then restart " +
                        "Scarlet Crystal and attempt sign-in once. Existing pairing, certificates, " +
                        "apps and account data have not been reset.",
                        comment: "Non-destructive Anisette authentication recovery")
                    completionHandler(.failure(NSError(
                        domain: "ScarletCrystal.AnissetteAuthentication", code: -80045,
                        userInfo: [NSLocalizedDescriptionKey: detail])))
                } else {
                    completionHandler(.failure(error))
                }
"""

def once(src, old, new, label):
    actual = src.count(old)
    if actual != 1:
        raise ValueError(f"V181 {label}: expected one exact upstream anchor, found {actual}")
    return src.replace(old, new, 1)

def patch_sidesign(source):
    if MARK in source:
        for name in ("scarletV181CompatibleUserAgent", NEW_GSA, NEW_2FA):
            if name not in source:
                raise ValueError("V181 partially applied in SideSign")
        return source
    if "import GSACryptoKit" not in source:
        raise ValueError("latest SideSign GrandSlam code not found")
    out = once(source, "import GSACryptoKit\n", "import GSACryptoKit\n" + HELPER, "helper")
    out = once(out, OLD_GSA, NEW_GSA, "GrandSlam default UA")
    out = once(out, OLD_2FA, NEW_2FA, "2FA default UA")
    if out.count(NEW_GSA) != 1 or out.count(NEW_2FA) != 1:
        raise ValueError("incomplete GrandSlam / 2FA profile parity")
    return out

def patch_handler(source):
    if MARK in source:
        if NEW_HANDLER not in source:
            raise ValueError("V181 partially applied in sign-in UI")
        return source
    if "import SideSign" not in source:
        raise ValueError("SideStore SignInFlowHandler no longer imports SideSign")
    return once(source, OLD_HANDLER, NEW_HANDLER, "error mapping")

def apply(side):
    paths = [(side / SIDESIGN, patch_sidesign), (side / HANDLER, patch_handler)]
    staged = []
    for path, fn in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError("missing upstream authentication source: " + str(path))
        original = path.read_text(encoding="utf-8")
        updated = fn(original)
        if fn(updated) != updated:
            raise ValueError("non-idempotent V181 authentication forward port")
        staged.append((path, original, updated))
    for path, original, updated in staged:
        if updated != original:
            path.write_text(updated, encoding="utf-8")
    print("[PASS] V181 GSA and 2FA UA parity, user overrides preserved, -80045 actionable")
    print("[UNVERIFIED] Apple live sign-in and user-specific 2FA cannot be confirmed by CI")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("sidestore", type=Path)
    args = p.parse_args()
    apply(args.sidestore.resolve())
