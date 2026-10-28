#!/usr/bin/env python3
"""V154 minimal source patch: recent glass, outside hit test, Direct tap."""
from pathlib import Path
import sys
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
BOOT=Path("LiveContainer/LCBootstrap.m")
SHELL=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
def replace(s,a,b,name):
    if s.count(a)!=1: raise ValueError(f"{name}: {s.count(a)} anchors")
    return s.replace(a,b,1)
def dock(s):
    if "SCARLET_V154_OUTSIDE_BACKDROP" in s:
        if "SCARLET_V154_RECENT_INSETS" not in s:raise ValueError("partial")
        return s
    cls="""// SCARLET_V154_OUTSIDE_BACKDROP: one existing overlay with a direct touch fallback.
private final class SCOutsideDismissBackdrop: UIControl {
    weak var activePanel: UIView?
    var dismissOutside: (() -> Void)?
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        if let touch = touches.first, let panel = activePanel {
            let outside = !panel.frame.contains(touch.location(in: self))
            NSLog("[SCARLET_V154_OUTSIDE] stage=backdrop_touch outside=%d", outside ? 1 : 0)
            if outside {
                DispatchQueue.main.async { [weak self] in self?.dismissOutside?() }
            }
        }
        super.touchesBegan(touches, with: event)
    }
}
"""
    s=replace(s,"private final class SCOutsideTouchDownRecognizer:",cls+"private final class SCOutsideTouchDownRecognizer:","class")
    s=replace(s,"let overlay = UIControl(frame: owner.bounds)","let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)","overlay")
    s=replace(s,"        overlay.addSubview(material)\n","        overlay.addSubview(material)\n        overlay.activePanel = material\n","panel")
    s=replace(s,"        }, for: .touchDown)\n        let outsideObserver",'''        }, for: .touchDown)
        overlay.dismissOutside = { collapse({}) }
        let outsideObserver''',"dismiss")
    s=replace(s,"        rows.translatesAutoresizingMaskIntoConstraints = false\n        scroll.addSubview(rows)",'''        rows.translatesAutoresizingMaskIntoConstraints = false
        // SCARLET_V154_RECENT_INSETS: room for native glass lens on recent rows ONLY.
        rows.isLayoutMarginsRelativeArrangement = !windowActions && !directMode
        rows.layoutMargins = UIEdgeInsets(top: 6, left: 12, bottom: 6, right: 12)
        scroll.addSubview(rows)''',"recent margin")
    s=replace(s,"            scroll.clipsToBounds = windowActions || directMode\n            let count = directMode ? 2",'''            scroll.clipsToBounds = windowActions || directMode
            rows.isLayoutMarginsRelativeArrangement = !windowActions && !directMode
            let count = directMode ? 2''',"tab margins")
    return s
def boot(s):
    if "SCARLET_V154_DIRECT_TAP_RECOGNIZER" in s:return s
    s=replace(s,'@property(nonatomic, strong) NSMutableDictionary<NSString *, SCGuestMorphWindow *> *windows;',
       '@property(nonatomic, strong) NSMutableDictionary<NSString *, SCGuestMorphWindow *> *windows;\n@property(nonatomic, assign) NSTimeInterval lastDirectOpen;',"property")
    s=replace(s,'    [handle addTarget:self action:@selector(openShared:) forControlEvents:UIControlEventTouchUpInside];',
'''    // SCARLET_V154_DIRECT_TAP_RECOGNIZER: additional event recognizer on SAME button.
    [handle addTarget:self action:@selector(openShared:) forControlEvents:UIControlEventTouchUpInside];
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc]
        initWithTarget:self action:@selector(openSharedTap:)];
    tap.cancelsTouchesInView = NO;
    tap.delaysTouchesBegan = NO;
    [handle addGestureRecognizer:tap];''',"button tap")
    s=replace(s,'- (void)openShared:(UIButton *)sourceView {\n',
'''- (void)openSharedTap:(UITapGestureRecognizer *)gesture {
    if (gesture.state == UIGestureRecognizerStateEnded) {
        NSLog(@"[SCARLET_V154_DIRECT] stage=tap_recognized");
        NSLog(@"[SCARLET_V154_DIRECT_TAP_RECOGNIZER] tap=recognized");
        [self openShared:(UIButton *)gesture.view];
    }
}
- (void)openShared:(UIButton *)sourceView {
''',"tap entry")
    s=replace(s,'    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");',
'''    NSTimeInterval now = [[NSDate date] timeIntervalSince1970];
    if (now - self.lastDirectOpen < 0.35) {
        NSLog(@"[SCARLET_V154_DIRECT] stage=deduplicated"); return;
    }
    self.lastDirectOpen = now;
    NSLog(@"[SCARLET_V154_DIRECT] stage=source_button_accepted");
    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");''',"single event")
    return s
def shell(s):
    if "SCARLET_V154_DIRECT_VISIBLE_CHECK" in s:return s
    s=replace(s,'''                    let scene = UIApplication.shared.connectedScenes
                        .compactMap { $0 as? UIWindowScene }
                        .first { $0.activationState == .foregroundActive }
                    guard let hostWindow = scene?.windows.first(where: {
                        !$0.isHidden && $0.windowLevel == .normal &&
                        $0.rootViewController != nil && $0.alpha > 0.01
                    }), let root = hostWindow.rootViewController,
                    root.view.window === hostWindow else {''',
'''                    // SCARLET_V154_DIRECT_VISIBLE_CHECK: priority is the
                    // *attached* foreground key host window. Xcode 27.2
                    // cannot type-check the previous chained Set<UIScene>
                    // compactMap/filter/flatMap/filter expression.
                    // SCARLET_V154_DIRECT_XCODE_SIMPLE_LOOP: avoid generic
                    // inference and keep each UIKit guard explicit.
                    var keyHostWindow: UIWindow? = nil
                    var firstHostWindow: UIWindow? = nil
                    for candidateScene in UIApplication.shared.connectedScenes {
                        guard let activeScene = candidateScene as? UIWindowScene else {
                            continue
                        }
                        guard activeScene.activationState == .foregroundActive else {
                            continue
                        }
                        for candidateWindow in activeScene.windows {
                            guard !candidateWindow.isHidden else { continue }
                            guard candidateWindow.windowLevel == .normal else { continue }
                            guard candidateWindow.alpha > 0.01 else { continue }
                            guard let candidateRoot = candidateWindow.rootViewController else {
                                continue
                            }
                            guard candidateRoot.view.window === candidateWindow else { continue }
                            if firstHostWindow == nil {
                                firstHostWindow = candidateWindow
                            }
                            if candidateWindow.isKeyWindow {
                                keyHostWindow = candidateWindow
                                break
                            }
                        }
                        if keyHostWindow != nil { break }
                    }
                    guard let hostWindow = keyHostWindow ?? firstHostWindow,
                          let root = hostWindow.rootViewController else {''',"host")
    s=replace(s,'                        delivered = true\n                        // SCARLET_V153_DIRECT_HOST_PICKER:',
                   '                        // SCARLET_V153_DIRECT_HOST_PICKER:',"early success")
    s=replace(s,'''                        NSLog("[SCARLET_V147_DIRECT] route=host result=presented")
                        NSLog("[SCARLET_V153_DIRECT] route=host mode=direct picker=invoked")''',
'''                        NSLog("[SCARLET_V153_DIRECT] route=host mode=direct picker=invoked")
                        let visible = hostWindow.subviews.contains {
                            $0.accessibilityIdentifier == "scarlet.v100.morph.backdrop" &&
                            !$0.isHidden && $0.alpha > 0.001
                        }
                        if visible {
                            delivered = true
                            NSLog("[SCARLET_V154_DIRECT] stage=panel_visible result=1")
                            NSLog("[SCARLET_V147_DIRECT] route=host result=presented")
                        } else {
                            NSLog("[SCARLET_V154_DIRECT] stage=panel_visible result=0 retry=1")
                        }''',"real visibility")
    return s
def apply(root):
    output=[]
    for path,fn in [(DOCK,dock),(BOOT,boot),(SHELL,shell)]:
        f=root/path
        before=f.read_text();after=fn(before)
        if fn(after)!=after:raise ValueError("not idempotent "+str(path))
        output.append((f,before,after))
    for f,before,after in output:
        if before!=after:f.write_text(after)
    print("V154_PATCH_PASS")
if __name__=="__main__":apply(Path(sys.argv[1]))
