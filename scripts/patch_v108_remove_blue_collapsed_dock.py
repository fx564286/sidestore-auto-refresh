#!/usr/bin/env python3
"""Remove the obsolete blue collapsed Dock UI in the final generated source."""

from pathlib import Path
import sys

FILE = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "SCARLET_V108_NO_BLUE_COLLAPSED_DOCK"

def replace(s, old, new, label):
    if s.count(old) != 1:
        raise ValueError(f"V108 {label}: wanted one anchor, got {s.count(old)}")
    return s.replace(old, new, 1)

def patch(s):
    if MARK in s:
        audit(s)
        return s
    # Delete both FULL obsolete view declarations, not just their visibility.
    head = "// MARK: - Collapsed Dock View\n"
    tail = "// MARK: - Minimize All Button View\n"
    if s.count(head) != 1 or s.count(tail) != 1:
        raise ValueError("V108 old Dock definitions changed")
    a, b = s.index(head), s.index(tail)
    old = s[a:b]
    if a >= b or "struct CollapsedDockView: View" not in old or "struct CollapseButtonView: View" not in old:
        raise ValueError("V108 old Dock controls do not match reviewed source")
    s = s[:a] + s[b:]
    # Keep only the live guest switcher (the native window overflow stays).
    begin = s.index("    public var body: some View {", s.index("public struct MultitaskDockSwiftView: View"))
    end = s.index("\n\n\n        .ignoresSafeArea()", begin)
    body = s[begin:end]
    for token in ("if dockManager.isCollapsed {", "CollapsedDockView(isHidden:",
                  "CollapseButtonView()", "ForEach(dockManager.apps) { app in",
                  ".modifier { content in", ".position(x: g.size.width / 2, y: g.size.height / 2)"):
        if token not in body:
            raise ValueError("V108 Dock body changed: " + token)
    decorate = body[body.index("            .padding(dynamicPadding)"):]
    if ".position(x: g.size.width / 2, y: g.size.height / 2)" not in decorate or "\n        }" not in decorate:
        raise ValueError("V108 unexpected Dock modifier chain")
    decorate = decorate[:decorate.rindex("\n        }")]
    decorate = decorate.replace(
        ".opacity(dockManager.isDockHidden ? (hideCollapsedDock && dockManager.isCollapsed ? 0.01 : 0.4) : 1.0)",
        ".opacity(dockManager.isDockHidden ? 0.0 : 1.0)")
    body = """    public var body: some View {
        GeometryReader { g in
            dockManager.v3RecordFirstDockBodyEvaluation()
            // SCARLET_V108_NO_BLUE_COLLAPSED_DOCK: truly empty when tucked.
            // Edge swipe reveals the existing, installed live guest icons.
            if dockManager.v3DockPresentationState.isReady &&
               !dockManager.isDockHidden && !dockManager.apps.isEmpty {
                VStack(spacing: 8) {
                    ForEach(dockManager.apps) { app in
                        AppIconView(app: app)
                    }
                }
                .onAppear { dockManager.v3RecordFirstRenderedDockView(.expandedDockView) }
""" + decorate + """
            }
        }"""
    s = s[:begin] + body + s[end:]
    s = replace(s,
        '    @AppStorage("LCHideCollapsedDock", store: LCUtils.appGroupUserDefault) var hideCollapsedDock: Bool = false\n',
        '', "obsolete collapsed-binding")
    s = replace(s,
        '        if isCollapsed {\n            let collapsedHeight = collapsedDockHeight(for: width)\n            return max(Constants.minCollapsedHeight, collapsedHeight)\n        } else {\n            let currentIconSize = calculateIconSize(for: width)\n            return expandedDockHeight(for: width, iconSize: currentIconSize)\n        }',
        '        let currentIconSize = calculateIconSize(for: width)\n        return expandedDockHeight(for: width, iconSize: currentIconSize)',
        "old collapsed height")

    # Migrate exactly one obsolete UI preference into the supported tuck
    # setting. This touches no guest storage, account, JIT, or signing data.
    s = replace(s,
        '        let stored = LCUtils.appGroupUserDefault.bool(forKey: "LCMultitaskDockStartsCollapsed")\n        self.isCollapsed = stored',
        '''        let prefs = LCUtils.appGroupUserDefault
        let oldCollapsed = prefs.bool(forKey: "LCMultitaskDockStartsCollapsed")
        if oldCollapsed && !prefs.bool(forKey: "LCMultitaskDockStartsTuckedToEdge") {
            prefs.set(true, forKey: "LCMultitaskDockStartsTuckedToEdge")
        }
        prefs.removeObject(forKey: "LCMultitaskDockStartsCollapsed")
        let stored = false
        self.isCollapsed = false
        NSLog("[SCARLET_V108_DOCK] blue_collapsed_ui_deleted=1 edge_swipe_guest_list=1")''',
        "one-time legacy collapse preference migration")
    # Existing collapsed preference now means edge-tucked/no drawn button.
    # Leave the user's stored preference untouched, and reveal real app icons.
    old = 'if let initialHidden = self.collapseStartState.applyTuckedBeforeFirstFrame(sessionID: sessionID) { self.isDockHidden = initialHidden }'
    if s.count(old) != 3:
        raise ValueError("V108 session state drift: " + str(s.count(old)))
    s = s.replace(old,
        'if let initialHidden = self.collapseStartState.applyTuckedBeforeFirstFrame(sessionID: sessionID) { self.isDockHidden = initialHidden || self.isCollapsed }')
    s = replace(s,
        '            self.isCollapsed.toggle()\n            self.updateDockFrame()\n            self.notifyDockCollapseChanged()',
        '''            // No collapsed button: toggling tucks or reveals real guest icons.
            self.isCollapsed = false
            self.isDockHidden.toggle()
            self.updateDockFrame()
            self.setupEdgeGestureRecognizers()
            self.notifyDockCollapseChanged()''', "manual collapse replacement")
    s = replace(s,
        '            self.isDockHidden = false\n            self.updateDockFrame()\n            self.setupEdgeGestureRecognizers()',
        '            self.isCollapsed = false\n            self.isDockHidden = false\n            self.updateDockFrame()\n            self.setupEdgeGestureRecognizers()',
        "side-swipe revealing full Dock")
    # Do not strip unrelated UITapGestureRecognizer from the entire host.
    s = replace(s,
        '    @Published var isDockHidden: Bool = false\n',
        '''    @Published var isDockHidden: Bool = false
    private weak var nrgV108LeftEdgeGesture: UIScreenEdgePanGestureRecognizer?
    private weak var nrgV108RightEdgeGesture: UIScreenEdgePanGestureRecognizer?
''', "owned recognizers")
    old = '''        keyWindow.gestureRecognizers?.removeAll { gesture in
            return gesture is UITapGestureRecognizer || gesture is UIScreenEdgePanGestureRecognizer
        }
        
        if isDockHidden {
            let leftEdgeGesture = UIScreenEdgePanGestureRecognizer(target: self, action: #selector(handleEdgeSwipe(_:)))
            leftEdgeGesture.edges = .left
            keyWindow.addGestureRecognizer(leftEdgeGesture)
            
            let rightEdgeGesture = UIScreenEdgePanGestureRecognizer(target: self, action: #selector(handleEdgeSwipe(_:)))
            rightEdgeGesture.edges = .right
            keyWindow.addGestureRecognizer(rightEdgeGesture)
        }'''
    new = '''        // Remove only this Dock's previous edge recognizers.
        if let previous = nrgV108LeftEdgeGesture {
            previous.view?.removeGestureRecognizer(previous)
        }
        if let previous = nrgV108RightEdgeGesture {
            previous.view?.removeGestureRecognizer(previous)
        }
        nrgV108LeftEdgeGesture = nil
        nrgV108RightEdgeGesture = nil
        if isDockHidden {
            let leftEdgeGesture = UIScreenEdgePanGestureRecognizer(target: self, action: #selector(handleEdgeSwipe(_:)))
            leftEdgeGesture.edges = .left
            keyWindow.addGestureRecognizer(leftEdgeGesture)
            nrgV108LeftEdgeGesture = leftEdgeGesture
            let rightEdgeGesture = UIScreenEdgePanGestureRecognizer(target: self, action: #selector(handleEdgeSwipe(_:)))
            rightEdgeGesture.edges = .right
            keyWindow.addGestureRecognizer(rightEdgeGesture)
            nrgV108RightEdgeGesture = rightEdgeGesture
        }'''
    s = replace(s, old, new, "host-safe edge recognizers")
    s = replace(s,
        '''        guard isDockHidden, gesture.state == .began || gesture.state == .changed else {
            return
        }
        
        let translation = gesture.translation(in: gesture.view)
        let swipeDistance = abs(translation.x)
        
        if swipeDistance > Constants.edgeSwipeThreshold {
            showDockFromHidden()
        }''',
        '''        guard isDockHidden, (gesture.state == .began || gesture.state == .changed) else { return }
        let swipeX = gesture.translation(in: gesture.view).x
        let inward = (gesture.edges == .left && swipeX > Constants.edgeSwipeThreshold)
                   || (gesture.edges == .right && swipeX < -Constants.edgeSwipeThreshold)
        if inward { showDockFromHidden() }''',
        "inward edge swipe")
    s = s.replace('"CollapsedDockView"', '"LegacyCollapsedPreference"')
    audit(s)
    return s

def audit(s):
    for marker in (MARK, "ForEach(dockManager.apps) { app in",
                   "if dockManager.v3DockPresentationState.isReady &&",
                   "!dockManager.isDockHidden && !dockManager.apps.isEmpty",
                   "nrgV108LeftEdgeGesture", "initialHidden || self.isCollapsed",
                   "guard controller is DecoratedAppSceneViewController",
                   "nrgV102PresentWindowActionsFrom"):
        if marker not in s:
            raise ValueError("V108 required surviving route missing: " + marker)
    for old in ("struct CollapsedDockView: View", "struct CollapseButtonView: View",
                "CollapsedDockView(isHidden:", "CollapseButtonView()",
                'Image(systemName: "chevron.up")', "hideCollapsedDock",
                "keyWindow.gestureRecognizers?.removeAll",
                "if dockManager.isCollapsed {"):
        if old in s:
            raise ValueError("V108 obsolete rendered UI not fully deleted: " + old)

SETTINGS = Path("LiveContainerSwiftUI/Views/Settings/LCMultitaskSettingView.swift")

def patch_settings(source):
    if "Start Dock Collapsed" not in source and "hideCollapsedDock" not in source:
        audit_settings(source)
        return source
    for old in (
        '    @AppStorage("LCHideCollapsedDock", store: LCUtils.appGroupUserDefault) var hideCollapsedDock: Bool = false\n',
        '    @AppStorage("LCMultitaskDockStartsCollapsed", store: LCUtils.appGroupUserDefault) var dockStartsCollapsed = false\n',
        '                Toggle(isOn: $dockStartsCollapsed) {\n                    Text("Start Dock Collapsed")\n                }\n',
        '                Toggle(isOn: $hideCollapsedDock) {\n                    Text("lc.settings.hideCollapsedDock".loc)\n                }\n',
    ):
        source = replace(source, old, "", "obsolete collapsed setting UI")
    old = 'Text("Start Dock Collapsed chooses the first expanded or collapsed dock view. Start Dock Tucked To Edge begins that fresh session in the existing hidden-to-side state; the edge control can bring it back. Both choices apply once per fresh session, so your later dock actions remain in effect through rotation. Hide Collapsed Dock controls visibility of an already-tucked collapsed dock.")'
    source = replace(source, old,
        'Text("Start Dock Tucked To Edge hides the Dock without a floating button. Swipe inward from the left or right edge to reveal the running guest app list. Existing window controls remain available from the window overflow.")',
        "legacy setting footer")
    audit_settings(source)
    return source

def audit_settings(source):
    for dead in ("hideCollapsedDock", "dockStartsCollapsed",
                 "Start Dock Collapsed", "LCHideCollapsedDock"):
        if dead in source:
            raise ValueError("V108 obsolete Dock setting survived: " + dead)
    if "Start Dock Tucked To Edge" not in source:
        raise ValueError("V108 retained edge-tuck setting missing")

def apply(root):
    file = root / FILE
    if not file.is_file() or file.is_symlink():
        raise ValueError("V108 pinned source missing")
    settings = root / SETTINGS
    if not settings.is_file() or settings.is_symlink():
        raise ValueError("V108 pinned settings file missing")
    before = file.read_text(encoding="utf-8")
    before_settings = settings.read_text(encoding="utf-8")
    after = patch(before)
    after_settings = patch_settings(before_settings)
    if patch(after) != after or patch_settings(after_settings) != after_settings:
        raise ValueError("V108 cleanup not idempotent")
    if before != after:
        file.write_text(after, encoding="utf-8")
    if before_settings != after_settings:
        settings.write_text(after_settings, encoding="utf-8")
    print("[PASS] V108 deleted blue/gray Dock views and obsolete settings; retained guest rows")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v108_remove_blue_collapsed_dock.py <LiveContainer>")
    apply(Path(sys.argv[1]))
