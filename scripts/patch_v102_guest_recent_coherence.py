#!/usr/bin/env python3
"""V102: coherent recent activation order and exclusive right-edge dock/picker.

Run strictly after the pinned V100 morph patch; no guest process, bundle, UI
container, signing identity, refresh or profile mutations.
"""
from pathlib import Path
import sys

FILE = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "SCARLET_V102_RECENT_FOCUS_CLOCK"

def one(source, old, new, label):
    n = source.count(old)
    if n != 1: raise ValueError(f"V102 {label}: expected exactly one anchor, got {n}")
    return source.replace(old, new, 1)

def patch(source):
    if MARK in source:
        required = ('nrgV102FocusDates', 'nrgV102NoteFocus', 'dockView?.isHidden = true',
                    'dockView?.isHidden = previousDockHidden', 'lhs.used != rhs.used')
        if source.count(MARK) != 1 or any(x not in source for x in required):
            raise ValueError("V102 incomplete or edited patch")
        return source
    for marker in ("SCARLET_V100_MORPH_PICKER",
                   "SCARLET_V97_RETAINED_GUEST_HOST_REBIND",
                   "NRG_V72_OVERFLOW_LONGPRESS"):
        if marker not in source: raise ValueError(f"V102 missing prerequisite {marker}")
    source = one(source,
        '    @Published var apps: [DockAppModel] = []',
        '''    @Published var apps: [DockAppModel] = []
    // SCARLET_V102_RECENT_FOCUS_CLOCK: actual switch-to-foreground events.
    // V72's lastLaunched is only launch time and cannot order retained scenes.
    // Keep an in-memory map; never rewrite persistent guest installation data.
    private var nrgV102FocusDates: [String: Date] = [:]
    func nrgV102NoteFocus(_ folder: String) {
        guard Thread.isMainThread && !folder.isEmpty else { return }
        nrgV102FocusDates[folder] = Date()
        // Keep the right-edge Dock's visible order synchronized with the
        // picker: most recently focused window is last (Dock is trailing).
        if let index = apps.firstIndex(where: { $0.appUUID == folder }) {
            let active = apps.remove(at: index)
            apps.append(active)
        }
    }''', "focus clock")
    source = one(source,
        '            self.apps.append(appModel)',
        '''            self.nrgV102NoteFocus(appUUID)
            self.apps.append(appModel)''',
        "new running dock app focus")
    source = one(source,
        '        animateViewAppearance(targetView, from: center, in: window)',
        '''        animateViewAppearance(targetView, from: center, in: window)
        // V102: refocusing a retained view counts as actual recent use.
        nrgV102NoteFocus(uuid)''',
        "same-scene refocus")
    source = one(source,
        '''            // Do not confuse all installed guests with recently used guests.
            guard isRunning || (used <= current && current.timeIntervalSince(used) < 48 * 60 * 60) else {
                return nil
            }''',
        '''            // V102: only currently retained live guests belong in the
            // quick switcher, matching the right-edge Dock's membership.
            // A lastLaunched timestamp alone never makes an app "running".
            guard isRunning else { return nil }''', "retire 48h installed-app history")
    source = one(source, '        let current = Date()\n', '', "remove unused old clock")
    source = one(source,
        '            let used = model.appInfo.lastLaunched ?? .distantPast',
        '''            // Unlike V72, prefer real foreground focus of the SAME
            // UI container shown in the right-edge dock. Preserve older
            // lastLaunched as a fallback for nonrunning LiveProcess guests.
            let used = max(model.appInfo.lastLaunched ?? .distantPast,
                           nrgV102FocusDates[folder] ?? .distantPast)''',
        "recent candidates")
    source = one(source,
        '''            if lhs.running != rhs.running { return lhs.running }
            if lhs.used != rhs.used { return lhs.used > rhs.used }
            return lhs.name < rhs.name''',
        '''            // Actual focus order wins; a long-running background guest
            // must not leap ahead of the app the user just switched to.
            if lhs.used != rhs.used { return lhs.used > rhs.used }
            if lhs.running != rhs.running { return lhs.running }
            return lhs.name < rhs.name''',
        "sort by real recency")
    source = one(source,
        '        let candidates = models.compactMap { model -> (name: String, bundle: String, route: URL, folder: String, running: Bool, used: Date)? in',
        '        let candidates = models.compactMap { model -> (name: String, bundle: String, folder: String, running: Bool, used: Date)? in', 'remove inactive route field')
    source = one(source,
        '            var components = URLComponents()\n            components.scheme = "scarletcrystal251"\n            components.host = "livecontainer-launch"\n            components.queryItems = [\n                URLQueryItem(name: "bundle-name", value: bundle),\n                URLQueryItem(name: "container-folder-name", value: folder),\n                URLQueryItem(name: "nrg-multitask", value: "1")\n            ]\n            guard let url = components.url else { return nil }\n            return (name: model.appInfo.displayName(), bundle: bundle, route: url,\n                    folder: folder, running: isRunning, used: used)',
        '            return (name: model.appInfo.displayName(), bundle: bundle,\n                    folder: folder, running: isRunning, used: used)', 'remove unused URL components')
    source = one(source,
        '        let recent = Array(candidates.filter { seen.insert($0.folder).inserted }.prefix(8))',
        '''        let recent = Array(candidates.filter { seen.insert($0.folder).inserted }.prefix(8))
        NSLog("[SCARLET_V102_RECENT] dock=%ld candidates=%ld recent=%ld order=foreground_focus",
              apps.count, candidates.count, recent.count)''',
        "count verified recents")
    source = one(source,
        '        owner.addSubview(overlay)\n\n        let material = UIVisualEffectView',
        '''        owner.addSubview(overlay)
        // Exclusivity: the edge Dock and picker share live guest membership,
        // but never paint two separate lists on top of the same guest scene.
        // Snapshot the user's prior Dock visibility; restore exactly on close.
        let dockView = hostingController?.view
        let previousDockHidden = dockView?.isHidden ?? false
        if dockView?.window?.windowScene === owner.windowScene {
            dockView?.isHidden = true
        }

        let material = UIVisualEffectView''',
        "one visible guest list")
    source = one(source,
        '''                backdrop.removeFromSuperview()
                if sourceView?.window != nil { sourceView?.isHidden = false }
                completion()''',
        '''                backdrop.removeFromSuperview()
                if dockView?.window?.windowScene === owner.windowScene {
                    dockView?.isHidden = previousDockHidden
                }
                // Never strand the trigger permanently hidden if switching
                // scenes detaches its window before the collapse completion.
                sourceView?.isHidden = false
                completion()''',
        "restore dock on dismiss")
    source = one(source,
        '''                            NSLog("[SCARLET_V100_MORPH] action=resume route=native")
                            return''',
        '''                            self.nrgV102NoteFocus(guest.folder)
                            NSLog("[SCARLET_V100_MORPH] action=resume route=native")
                            return''',
        "native window activation")
    source = one(source,
        '''                        NSLog("[SCARLET_V100_MORPH] action=blocked reason=retained_window_missing")''',
        '''                        NSLog("[SCARLET_V100_MORPH] action=blocked reason=retained_window_missing")''',
        "guarded old guest")

    source = one(source,
        '                    UIApplication.shared.open(guest.route, options: [:]) { accepted in\n                        NSLog("[SCARLET_V100_MORPH] action=recent_route accepted=%d", accepted ? 1 : 0)\n                    }',
        '                    NSLog("[SCARLET_V102_RECENT] no_inactive_launch_path=1")', 'retire nonrunning guest relaunch')
    return source

def main(root):
    target=root/FILE
    if not target.is_file() or target.is_symlink(): raise ValueError("missing pinned generated source")
    current=target.read_text(encoding='utf-8')
    updated=patch(current)
    if patch(updated)!=updated: raise ValueError("V102 not idempotent")
    if updated!=current:target.write_text(updated,encoding='utf-8')
    print("[PASS] V102 focus-based recent apps; edge dock hidden only while morph shown")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v102_guest_recent_coherence.py <LiveContainer root>")
    main(Path(sys.argv[1]))
