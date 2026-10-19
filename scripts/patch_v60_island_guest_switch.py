#!/usr/bin/env python3
"""V60: route real ActivityKit guest shortcuts through LiveContainer's guest launch path.

Native system Island only. Preserve signed host, JIT, saved containers, and
multitasking window ownership. Never simulate an iOS system touch surface.
"""
from pathlib import Path
import sys

MARK = "NRG_V60_ISLAND_ROUTE"
SHELL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
APPS = Path("LiveContainerSwiftUI/Views/AppList/LCAppListView.swift")

def one(text, original, replacement, label):
    matches = text.count(original)
    if matches != 1:
        raise RuntimeError(f"V60 {label}: expected one anchor, found {matches}")
    return text.replace(original, replacement, 1)

def patch_shell(s):
    if MARK in s:
        if s.count(MARK) != 2 or "nrg-apps" not in s:
            raise RuntimeError("V60 partial unified shell")
        return s
    s = one(s,
        "        .onOpenURL(perform: dispatchURL)\n",
        '''        // NRG_V60_ISLAND_ROUTE: start/update a native Live Activity while
        // the host is visible. No in-app overlay can capture the hardware notch.
        .onAppear { MultitaskDockManager.shared.nrgV58RefreshNativeIsland() }
        .onReceive(sharedModel.$apps) { _ in
            DispatchQueue.main.async {
                MultitaskDockManager.shared.nrgV58RefreshNativeIsland()
            }
        }
        .onOpenURL(perform: dispatchURL)
''', "start and refresh native Island")
    s = one(s,
        '''            case "livecontainer-launch", "install", "open-web-page", "open-url": sharedModel.selectedTab = .apps
''',
        '''            // NRG_V60_ISLAND_ROUTE: "all apps" is not a guest launch.
            case "nrg-apps":
                sharedModel.selectedTab = .apps
                return
            case "livecontainer-launch", "install", "open-web-page", "open-url": sharedModel.selectedTab = .apps
''', "all-installed destination")
    return s

def patch_apps(s):
    if MARK in s:
        if s.count(MARK) != 2 or "multitask: islandMultitask" not in s:
            raise RuntimeError("V60 partial app list")
        return s
    s = one(s,
        '''    func launchAppWithBundleId(bundleId : String, container : String?, urlStr: String? = nil, forceJIT: Bool? = nil) async {''',
        '''    // NRG_V60_ISLAND_ROUTE: opt-in retained scene for a system-Island tap;
    // ordinary app launches keep the user's existing launch preference.
    func launchAppWithBundleId(bundleId : String, container : String?, urlStr: String? = nil, forceJIT: Bool? = nil, multitask: Bool? = nil) async {''',
        "switch launch signature")
    s = one(s,
        '''            try await appFound.runApp(multitask: nil, containerFolderName: container, urlStr: urlStr, forceJIT: forceJIT)''',
        '''            try await appFound.runApp(multitask: multitask, containerFolderName: container, urlStr: urlStr, forceJIT: forceJIT)''',
        "guest execution")
    s = one(s,
        '''                var forceJIT: Bool? = nil
                var urlStr: String? = nil
                for queryItem in components.queryItems ?? [] {''',
        '''                var forceJIT: Bool? = nil
                var urlStr: String? = nil
                // NRG_V60_ISLAND_ROUTE: only the explicit native Island link
                // opts in to retained multitask windows.
                let islandMultitask: Bool? = components.queryItems?.contains {
                    $0.name == "nrg-multitask" && $0.value == "1"
                } == true ? true : nil
                for queryItem in components.queryItems ?? [] {''',
        "route opt-in")
    s = one(s,
        '''                    Task { await launchAppWithBundleId(bundleId: bundleId, container: containerName, urlStr: urlStr, forceJIT: forceJIT) }''',
        '''                    Task { await launchAppWithBundleId(bundleId: bundleId, container: containerName, urlStr: urlStr, forceJIT: forceJIT, multitask: islandMultitask) }''',
        "deep link switch")
    return s

def main(root):
    pending=[]
    for relative, transform in ((SHELL, patch_shell), (APPS, patch_apps)):
        file=root/relative
        old=file.read_text(encoding="utf-8")
        new=transform(old)
        if transform(new)!=new:
            raise RuntimeError(f"V60 patch non-idempotent: {relative}")
        pending.append((file,old,new))
    for file,old,new in pending:
        if old!=new:
            file.write_text(new, encoding="utf-8")
        print(f"[PASS] V60 native Island guest deep link: {file.relative_to(root)}")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v60_island_guest_switch.py <LiveContainer>")
    main(Path(sys.argv[1]))
