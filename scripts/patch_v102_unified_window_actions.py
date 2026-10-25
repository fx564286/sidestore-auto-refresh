#!/usr/bin/env python3
"""V102: remove obsolete V72 window long-press selector; share V100 morph surface.

One short tap -> recents; a 0.55s hold -> in-place window actions using the
same morph card/backdrop. All actions are explicit. No old UIAlertController
or separate floating menu survives in the final generated host source.
"""
from pathlib import Path
import sys
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
WINDOW=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK="SCARLET_V102_UNIFIED_ACTION_SURFACE"

def one(s,old,new,name):
    if s.count(old)!=1:
        raise ValueError(f"V102 {name}: expected 1; got {s.count(old)}")
    return s.replace(old,new,1)

def patch_dock(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'nrgV102WindowActionRequest' not in s:
            raise ValueError("partial V102 morph")
        return s
    if "SCARLET_V100_MORPH_PICKER" not in s or "SCARLET_V102_RECENT_FOCUS_CLOCK" not in s:
        raise ValueError("Requires V100 + V102 focus")
    s=one(s,"    private var nrgV102FocusDates: [String: Date] = [:]",
          """    private var nrgV102FocusDates: [String: Date] = [:]
    // SCARLET_V102_UNIFIED_ACTION_SURFACE: one renderer; two content modes.
    // No extra UIKit action sheet, duplicate FloatingWindow controller,
    // legacy button event, or simulated press on the guest.
    private var nrgV102WindowActionRequest = false
    @objc(nrgV102PresentWindowActionsFrom:sourceView:)
    public func nrgV102PresentWindowActions(from controller: UIViewController,
                                           sourceView: UIView) {
        guard Thread.isMainThread else {
            DispatchQueue.main.async { [weak self, weak controller, weak sourceView] in
                guard let controller, let sourceView else { return }
                self?.nrgV102PresentWindowActions(from: controller, sourceView: sourceView)
            }
            return
        }
        nrgV102WindowActionRequest = true
        defer { nrgV102WindowActionRequest = false }
        nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)
    }""","mode property and selector")
    s=one(s,'        let models = DataManager.shared.model.apps',
          '        let windowActions = nrgV102WindowActionRequest\n        let models = DataManager.shared.model.apps', "render mode")
    s=one(s, '              controller.view.window != nil,',
          '              (windowActions || controller.view.window != nil),', "native visible source")
    s=one(s, '        heading.text = "최근 실행 앱"',
          '        heading.text = windowActions ? "창 관리" : "최근 실행 앱"', "shared title")
    s=one(s, '        subtitle.text = "홍수정에 설치된 앱만 표시"',
          '        subtitle.text = windowActions ? "현재 게스트 창" : "홍수정 내부 · 최근 활성화 순"', "shared subtitle")
    s=one(s, '        scroll.showsVerticalScrollIndicator = recent.count > 5',
          '        scroll.showsVerticalScrollIndicator = !windowActions && recent.count > 5', "scroll")
    s=one(s, '        let listHeight = min(CGFloat(max(1, recent.count)) * 54, maxListHeight)',
          '''        let actionsCount = controller is DecoratedAppSceneViewController ? 3 : 2
        let listHeight = min(CGFloat(max(1, windowActions ? actionsCount : recent.count)) * 54, maxListHeight)''', "list height")
    s=one(s, '        if recent.isEmpty {\n            let empty = UILabel()',
          '        if recent.isEmpty && !windowActions {\n            let empty = UILabel()', "empty state")
    s=one(s, '        for guest in recent {\n            let item = UIButton(type: .system)',
          '        if !windowActions {\n        for guest in recent {\n            let item = UIButton(type: .system)', "recent only rows")
    s=one(s, '            rows.addArrangedSubview(item)\n        }\n\n        let footer = UILabel()',
          '''            rows.addArrangedSubview(item)
        }
        } else {
            // Same native system-material panel as recents. Invoke only the
            // existing, verified window action selectors on this controller.
            let actions: [(String, String)] =
                controller is DecoratedAppSceneViewController
                    ? [("최소화", "minimizeWindow"),
                       ("최대화 / 복원", "maximizeWindow"),
                       ("창 닫기", "closeWindow")]
                    : [("홍수정으로 돌아가기", "lcReturnToHost"),
                       ("버튼 접기", "lcV102CollapseFloatingButton")]
            for (title, selectorName) in actions {
                let item = UIButton(type: .system)
                item.contentHorizontalAlignment = .center
                item.titleLabel?.font = UIFont.systemFont(ofSize: 14, weight: .semibold)
                item.layer.cornerRadius = 15
                item.backgroundColor = UIColor.secondarySystemGroupedBackground
                item.setTitle(title, for: .normal)
                item.setTitleColor(.label, for: .normal)
                item.heightAnchor.constraint(equalToConstant: 47).isActive = true
                item.addAction(UIAction { _ in
                    collapse {
                        // No action can run against a detached/replaced scene.
                        guard sourceView.window != nil,
                              (controller.view.window != nil ||
                               !(controller is DecoratedAppSceneViewController)) else { return }
                        let selector = NSSelectorFromString(selectorName)
                        guard controller.responds(to: selector) else {
                            NSLog("[SCARLET_V102_ACTION] unsupported_selector=1")
                            return
                        }
                        _ = controller.perform(selector)
                    }
                }, for: .touchUpInside)
                rows.addArrangedSubview(item)
            }
        }

        let footer = UILabel()''', "window action rows")
    s=one(s, '        footer.text = "바깥 화면을 누르면 닫힙니다"',
          '        footer.text = windowActions ? "바깥을 누르면 창 관리 닫기" : "바깥을 누르면 앱 전환 닫기"', "footer")
    return s

def patch_window(s):
    if MARK in s:
        if s.count(MARK)!=1 or '- (void)nrgV72WindowOverflowLongPress:' in s:
            raise ValueError("V102 stale selector present")
        return s
    if "SCARLET_V100_TAP_OPEN" not in s:
        raise ValueError("Missing V100 control")
    # V37's UIMenu construction is obsolete: delete it rather than overriding.
    native_menu_start='    overflow.menu = [UIMenu menuWithChildren:@['
    if s.count(native_menu_start)!=1: raise ValueError("old V37 menu missing")
    a=s.index(native_menu_start)
    b=s.index('    ]];',a)+len('    ]];')
    legacy=s[a:b]
    if not all(x in legacy for x in ('minimizeWindow','maximizeWindow','closeWindow')):
        raise ValueError("Unexpected V37 actions; do not remove")
    s=s[:a]+s[b:]
    if s.count('    __weak typeof(self) weakOverflowSelf = self;') != 1:
        raise ValueError('old V37 weak menu capture not found')
    s=s.replace('    __weak typeof(self) weakOverflowSelf = self;', '', 1)
    s=one(s, '    overflow.showsMenuAsPrimaryAction = NO;',
          '''    // SCARLET_V102_UNIFIED_ACTION_SURFACE: no native UIMenu competing
    // with the custom morph on long-hold. Existing actions move into the
    // SAME reusable guest-panel material.
    overflow.menu = nil;
    overflow.showsMenuAsPrimaryAction = NO;
    UILongPressGestureRecognizer *nrgV102Hold = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(nrgV102HoldWindowActions:)];
    nrgV102Hold.minimumPressDuration = 0.55;
    nrgV102Hold.cancelsTouchesInView = YES;
    [overflow addGestureRecognizer:nrgV102Hold];''', "single hold")
    anchor='// V100: never synthesize a tap into the guest view itself.'
    method='''// V102: long-hold animates the same host-owned control to actions mode.
- (void)nrgV102HoldWindowActions:(UILongPressGestureRecognizer *)gesture {
    if (gesture.state != UIGestureRecognizerStateBegan ||
        !self.nrgWindowOverflow || !self.nrgWindowOverflow.window) return;
    UIImpactFeedbackGenerator *feedback = [[UIImpactFeedbackGenerator alloc]
        initWithStyle:UIImpactFeedbackStyleLight];
    [feedback impactOccurred];
    [MultitaskDockManager.shared nrgV102PresentWindowActionsFrom:self
                                                      sourceView:self.nrgWindowOverflow];
}

'''
    s=one(s,anchor,method+anchor,"hold method")
    signature='- (void)nrgV72WindowOverflowLongPress:(UILongPressGestureRecognizer *)gesture {'
    start=s.find(signature)
    if start<0 or s.count(signature)!=1:raise ValueError("V72 deprecated selector missing/duplicate")
    closing=s.find('\n}\n',start)
    if closing<0:raise ValueError("V72 selector incomplete")
    body=s[start:closing+3]
    if '[SCARLET_V100_MORPH] legacy_hold_not_installed=1' not in body:
        raise ValueError("Unknown old V72 body; refuse deletion")
    s=s[:start]+s[closing+3:]
    return s

def apply(root):
    files=[root/DOCK,root/WINDOW]
    if any(not p.is_file() or p.is_symlink() for p in files):raise ValueError("Missing pinned source")
    before=[p.read_text() for p in files]
    after=[patch_dock(before[0]),patch_window(before[1])]
    if patch_dock(after[0])!=after[0] or patch_window(after[1])!=after[1]:
        raise ValueError("Non-idempotent V102 action unification")
    for path,old,new in zip(files,before,after):
        if old!=new:path.write_text(new)
    print("[PASS] V102 retired unused V72 selector & redundant UIMenu; one morph for tap/hold")
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v102_unified_window_actions.py <LiveContainer>")
    apply(Path(sys.argv[1]))
