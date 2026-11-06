#!/usr/bin/env python3
"""Integrate a *navigation-only* SideStore sign-in deep link on pinned sources.

No new authentication implementation. The upstream native SettingsViewController
continues to own credential UI, Anisette, 2FA, portal session and sign-in.

Fail closed on a changed upstream source. Do not edit signing assets or
provisioning profiles. This patch is *not* evidence of live Apple login.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

PIN = "ee3cc16a67f9fed766f79a0ed70938f0f8ad5a07"
RELATIVE = "SideStore/DeepLinks/URLHandler.swift"
ROUTE_ANCHOR = '        case "install":\n'

ROUTE = '''        case "signin":
            // Scarlet's only job is to open the ORIGINAL SideStore sign-in
            // flow. Neither the host nor this adapter sees credentials/2FA.
            guard url.path.isEmpty || url.path == "/" else { return false }
            return ScarletOriginalSideStoreSignIn.open()

'''

ADAPTER = '''
// Built-in SideStore navigation adapter for Scarlet Crystal.
// No authentication, keychain, Anisette, certificate or 2FA code is replaced.
@MainActor
private enum ScarletOriginalSideStoreSignIn {
    private static func findSettings(in root: UIViewController) -> SettingsViewController? {
        if let settings = root as? SettingsViewController { return settings }
        if let nav = root as? UINavigationController {
            for child in nav.viewControllers {
                if let settings = findSettings(in: child) { return settings }
            }
        }
        for child in root.children {
            if let settings = findSettings(in: child) { return settings }
        }
        return nil
    }

    static func open() -> Bool {
        let scenes = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
        guard let root = scenes.flatMap(\\.windows)
            .first(where: { $0.isKeyWindow })?.rootViewController else {
            debugLog("[ScarletNativeSignIn] No foreground SideStore window")
            return false
        }

        // Reuse SideStore's existing Settings tab when it is already loaded.
        if let tab = root as? UITabBarController,
           let destinations = tab.viewControllers {
            for (index, destination) in destinations.enumerated() {
                if let settings = findSettings(in: destination) {
                    tab.selectedIndex = index
                    if !AuthManager.shared.isAuthenticated &&
                       settings.presentedViewController == nil {
                        DispatchQueue.main.async { settings.signIn() }
                    }
                    return true
                }
            }
        }

        // For embedded SideStore guest windows with no exposed tab controller,
        // instantiate the existing native Settings storyboard. We never
        // fabricate another Apple ID form or a separate verification handler.
        let storyboard = UIStoryboard(name: "Settings", bundle: nil)
        guard let navigation = storyboard.instantiateInitialViewController()
                as? UINavigationController,
              let settings = navigation.viewControllers.first
                as? SettingsViewController else {
            debugLog("[ScarletNativeSignIn] Original settings storyboard unavailable")
            return false
        }
        var presenter = root
        while let next = presenter.presentedViewController {
            presenter = next
        }
        guard !(presenter is UIAlertController) else { return false }
        navigation.modalPresentationStyle = .pageSheet
        presenter.present(navigation, animated: true) {
            if !AuthManager.shared.isAuthenticated {
                settings.signIn()
            }
        }
        return true
    }
}
'''

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def apply(source: str) -> str:
    if source.count(ROUTE_ANCHOR) != 1:
        raise RuntimeError("Pinned upstream login route insertion point changed")
    if "case \"signin\":" in source or "ScarletOriginalSideStoreSignIn" in source:
        raise RuntimeError("SideStore sign-in adapter is already present")
    if '@MainActor\nclass URLHandler {' not in source:
        raise RuntimeError("Pinned SideStore URLHandler isolation changed")
    if 'case "pairing":' not in source:
        raise RuntimeError("Original pairing flow missing; refuse patch")
    if 'URLComponents(url: url, resolvingAgainstBaseURL: false)' not in source:
        raise RuntimeError("Original SideStore URL decoder missing")
    return source.replace(ROUTE_ANCHOR, ROUTE + ROUTE_ANCHOR) + ADAPTER

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--engine",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    src=args.engine/RELATIVE
    assert src.is_file(),f"Original SideStore URLHandler missing: {src}"
    before=src.read_bytes()
    after=apply(before.decode("utf-8")).encode("utf-8")
    src.write_bytes(after)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    data={
       "schema":1,
       "upstreamPin":PIN,
       "modifiedFile":RELATIVE,
       "originalSha256":sha(before),"patchedSha256":sha(after),
       "onlyNavigationEntryPatched":True,
       "originalAuthManagerUnmodified":True,
       "originalSignInOperationUnmodified":True,
       "originalSignInFlowHandlerUnmodified":True,
       "originalTwoFactorUIUnmodified":True,
       "originalPairingUnmodified":True,
       "nativeSignInDeepLink":"sidestore://signin",
       "hostExpectedAction":"ScarletControl.serviceBeginSignIn",
       "actualAppleAuthenticationVerified":False,
       "status":"source integration only; live Apple authentication requires signed device test"
    }
    args.report.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print("[PASS] SideStore native sign-in URL entry uses original SettingsViewController/AuthManager/2FA")
    print("[BLOCK] Real Apple authentication, profile authorization, and device installation not verified")
if __name__=="__main__":
    main()
