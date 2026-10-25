#!/usr/bin/env python3
"""V100: morph existing draggable virtual-guest overflow button into inline guest picker.

Single tap opens a host-owned symmetric glass panel FROM the same button.
During presentation the triggering button is hidden. Tap empty backdrop to
collapse and restore that SAME button. The native UIMenu remains on long hold.
Do not modify guest ownership, geometry, JIT, or signing.
"""
from pathlib import Path
import sys

DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
WINDOW = Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK_DOCK = "SCARLET_V100_MORPH_PICKER"
MARK_WINDOW = "SCARLET_V100_TAP_OPEN"

START = '        let menu = UIAlertController(title: "홍수정 내부 앱 전환",'
END = '        NSLog("[NRG_V72_SWITCH] longpress=1 recent=%ld", recent.count)'
RENDER = r'''
        // SCARLET_V100_MORPH_PICKER: one host-owned surface replaces the
        // separate UIAlertController. The original button is the morph origin.
        guard let owner = sourceView.window,
              owner.windowScene?.activationState == .foregroundActive,
              controller.view.window != nil,
              sourceView.isHidden == false else { return }
        guard !owner.subviews.contains(where: {
            $0.accessibilityIdentifier == "scarlet.v100.morph.backdrop"
        }) else { return }

        let overlay = UIControl(frame: owner.bounds)
        overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        overlay.backgroundColor = UIColor.black.withAlphaComponent(0.32)
        overlay.alpha = 0
        owner.addSubview(overlay)

        let material = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))
        material.accessibilityIdentifier = "scarlet.v100.morph.panel"
        material.layer.cornerRadius = 26
        material.clipsToBounds = true
        material.translatesAutoresizingMaskIntoConstraints = false
        overlay.addSubview(material)

        let content = UIStackView()
        content.axis = .vertical
        content.spacing = 9
        content.alignment = .fill
        content.translatesAutoresizingMaskIntoConstraints = false
        material.contentView.addSubview(content)
        let availableWidth = max(260, owner.bounds.width - 48)
        let panelWidth = min(352, availableWidth)
        NSLayoutConstraint.activate([
            material.centerXAnchor.constraint(equalTo: overlay.centerXAnchor),
            material.centerYAnchor.constraint(equalTo: overlay.centerYAnchor),
            material.widthAnchor.constraint(equalToConstant: panelWidth),
            content.leadingAnchor.constraint(equalTo: material.contentView.leadingAnchor, constant: 17),
            content.trailingAnchor.constraint(equalTo: material.contentView.trailingAnchor, constant: -17),
            content.topAnchor.constraint(equalTo: material.contentView.topAnchor, constant: 20),
            content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -18)
        ])

        let heading = UILabel()
        heading.text = "최근 실행 앱"
        heading.font = UIFont.systemFont(ofSize: 18, weight: .semibold)
        heading.textColor = .label
        heading.textAlignment = .center
        content.addArrangedSubview(heading)

        let subtitle = UILabel()
        subtitle.text = "홍수정에 설치된 앱만 표시"
        subtitle.font = UIFont.systemFont(ofSize: 11, weight: .medium)
        subtitle.textColor = .secondaryLabel
        subtitle.textAlignment = .center
        content.addArrangedSubview(subtitle)

        let scroll = UIScrollView()
        scroll.showsVerticalScrollIndicator = recent.count > 5
        let rows = UIStackView()
        rows.axis = .vertical
        rows.spacing = 7
        rows.translatesAutoresizingMaskIntoConstraints = false
        scroll.addSubview(rows)
        NSLayoutConstraint.activate([
            rows.leadingAnchor.constraint(equalTo: scroll.contentLayoutGuide.leadingAnchor),
            rows.trailingAnchor.constraint(equalTo: scroll.contentLayoutGuide.trailingAnchor),
            rows.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor),
            rows.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor),
            rows.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor)
        ])
        content.addArrangedSubview(scroll)
        // Scrolling prevents guest controls from overflowing landscape/SE.
        let maxListHeight = max(60, owner.bounds.height - owner.safeAreaInsets.top -
                                  owner.safeAreaInsets.bottom - 170)
        let listHeight = min(CGFloat(max(1, recent.count)) * 54, maxListHeight)
        scroll.heightAnchor.constraint(equalToConstant: listHeight).isActive = true

        let sourceOrigin = sourceView.convert(sourceView.bounds, to: owner)
        // The same closure handles outside tap and guest selection.
        let collapse: (@escaping () -> Void) -> Void = { [weak overlay, weak material, weak sourceView] completion in
            guard let backdrop = overlay, backdrop.superview != nil,
                  let pane = material else { completion(); return }
            guard backdrop.isUserInteractionEnabled else { return }
            backdrop.isUserInteractionEnabled = false
            let reduceMotion = UIAccessibility.isReduceMotionEnabled
            UIView.animate(withDuration: reduceMotion ? 0.12 : 0.28,
                           delay: 0,
                           usingSpringWithDamping: 0.90,
                           initialSpringVelocity: 0,
                           options: [.beginFromCurrentState, .allowUserInteraction],
                           animations: {
                backdrop.alpha = 0
                pane.transform = reduceMotion ? .identity
                    : CGAffineTransform(translationX: sourceOrigin.midX - pane.center.x,
                                        y: sourceOrigin.midY - pane.center.y)
                        .scaledBy(x: 0.16, y: 0.16)
            }, completion: { _ in
                backdrop.removeFromSuperview()
                if sourceView?.window != nil { sourceView?.isHidden = false }
                completion()
            })
        }
        overlay.addAction(UIAction { _ in collapse({}) }, for: .touchUpInside)

        if recent.isEmpty {
            let empty = UILabel()
            empty.text = "최근 실행한 컨테이너 앱이 없습니다."
            empty.font = UIFont.systemFont(ofSize: 12)
            empty.textColor = .secondaryLabel
            empty.textAlignment = .center
            empty.numberOfLines = 2
            rows.addArrangedSubview(empty)
        }
        for guest in recent {
            let item = UIButton(type: .system)
            item.accessibilityIdentifier = "scarlet.v100.guest." + guest.folder
            item.accessibilityLabel = guest.name
            item.contentHorizontalAlignment = .left
            item.titleLabel?.font = UIFont.systemFont(ofSize: 14, weight: .medium)
            item.layer.cornerRadius = 15
            item.backgroundColor = UIColor.secondarySystemGroupedBackground
            item.setTitle((guest.running ? "●  " : "◌  ") + guest.name, for: .normal)
            item.setTitleColor(.label, for: .normal)
            item.titleEdgeInsets = UIEdgeInsets(top: 0, left: 13, bottom: 0, right: 12)
            item.heightAnchor.constraint(equalToConstant: 47).isActive = true
            item.addAction(UIAction { [weak self] _ in
                collapse {
                    guard let self else { return }
                    guard DataManager.shared.model.apps.contains(where: { model in
                        model.appInfo.relativeBundlePath == guest.bundle &&
                        model.uiContainers.contains(where: { $0.folderName == guest.folder })
                    }) else {
                        NSLog("[SCARLET_V100_MORPH] action=rejected reason=stale_guest")
                        return
                    }
                    // Resume existing windows before considering a route.
                    if guest.running {
                        if #available(iOS 16.1, *),
                           MultitaskWindowManager.openExistingAppWindow(dataUUID: guest.folder) {
                            NSLog("[SCARLET_V100_MORPH] action=resume route=native")
                            return
                        }
                        if self.bringMultitaskViewToFront(uuid: guest.folder) {
                            NSLog("[SCARLET_V100_MORPH] action=resume route=virtual")
                            return
                        }
                        // A retained live guest must never be duplicated.
                        NSLog("[SCARLET_V100_MORPH] action=blocked reason=retained_window_missing")
                        return
                    }
                    UIApplication.shared.open(guest.route, options: [:]) { accepted in
                        NSLog("[SCARLET_V100_MORPH] action=recent_route accepted=%d", accepted ? 1 : 0)
                    }
                }
            }, for: .touchUpInside)
            rows.addArrangedSubview(item)
        }

        let footer = UILabel()
        footer.text = "바깥 화면을 누르면 닫힙니다"
        footer.font = UIFont.systemFont(ofSize: 11)
        footer.textColor = .secondaryLabel
        footer.textAlignment = .center
        content.addArrangedSubview(footer)

        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
        let sourceCenter = CGPoint(x: sourceOrigin.midX, y: sourceOrigin.midY)
        let panelCenter = material.center
        let dx = sourceCenter.x - panelCenter.x
        let dy = sourceCenter.y - panelCenter.y
        let reduceMotion = UIAccessibility.isReduceMotionEnabled
        if !reduceMotion {
            material.transform = CGAffineTransform(translationX: dx, y: dy)
                .scaledBy(x: 0.16, y: 0.16)
        }
        sourceView.isHidden = true
        UIAccessibility.post(notification: .layoutChanged, argument: heading)
        UIView.animate(withDuration: reduceMotion ? 0.12 : 0.35,
                       delay: 0,
                       usingSpringWithDamping: 0.84,
                       initialSpringVelocity: 0.2,
                       options: [.beginFromCurrentState, .allowUserInteraction],
                       animations: {
            overlay.alpha = 1
            material.transform = .identity
        })
        NSLog("[SCARLET_V100_MORPH] action=expanded guests=%ld", recent.count)
'''

WINDOW_OLD = '''    overflow.showsMenuAsPrimaryAction = YES;
    UILongPressGestureRecognizer *nrgV72Hold = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(nrgV72WindowOverflowLongPress:)];
    nrgV72Hold.minimumPressDuration = 0.55;
    nrgV72Hold.cancelsTouchesInView = YES;
    [overflow addGestureRecognizer:nrgV72Hold];'''
WINDOW_NEW = '''    // SCARLET_V100_TAP_OPEN: one tap morphs this very button to the picker.
    // Preserve UIButton.menu for its native long-press window actions.
    overflow.showsMenuAsPrimaryAction = NO;
    [overflow addTarget:self action:@selector(nrgV100TapMorph:)
      forControlEvents:UIControlEventTouchUpInside];'''
WINDOW_METHOD = '''// V100: never synthesize a tap into the guest view itself.
- (void)nrgV100TapMorph:(UIButton *)sender {
    if (!sender || sender.hidden || !sender.window) return;
    [MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:self
                                                     sourceView:sender];
}

'''

def patch_dock(s):
    if MARK_DOCK in s:
        if s.count(MARK_DOCK) != 1 or START in s or "scarlet.v100.morph.backdrop" not in s:
            raise ValueError("V100 incomplete dock morph")
        return s
    if "SCARLET_V97_RETAINED_GUEST_HOST_REBIND" not in s:
        raise ValueError("V100 requires verified V97 host rebind")
    if s.count(START) != 1 or s.count(END) != 1:
        raise ValueError("V100 selector anchor drift")
    start=s.index(START)
    stop=s.index(END,start)+len(END)
    if s[start:stop].count("UIAlertController") < 1 or "guest.running" not in s[start:stop]:
        raise ValueError("V100 requires canonical V72/V87 guest picker")
    return s[:start]+RENDER.rstrip("\n")+s[stop:]

def patch_window(s):
    if MARK_WINDOW in s:
        if s.count(MARK_WINDOW) != 1 or WINDOW_OLD in s or "nrgV100TapMorph:" not in s:
            raise ValueError("V100 incomplete floating button patch")
        return s
    if "NRG_V73_APPLE_FLOATING_CONTROL" not in s or "NRG_V72_OVERFLOW_LONGPRESS" not in s:
        raise ValueError("V100 requires V72 and V73 native movable overflow")
    if s.count(WINDOW_OLD) != 1:
        raise ValueError(f"V100 old-gesture anchor drift: {s.count(WINDOW_OLD)}")
    method_anchor="- (void)nrgV72WindowOverflowLongPress:"
    if s.count(method_anchor)!=1:
        raise ValueError("V100 long-hold method anchor drift")
    s=s.replace(WINDOW_OLD,WINDOW_NEW,1)
    # The old V72 gesture is no longer installed. Retire its selector body
    # while keeping the required compatibility method declaration, so V88's
    # single canonical selector ownership check still remains valid.
    old_call='[MultitaskDockManager.shared nrgV72PresentGuestSwitcherFrom:self sourceView:self.nrgWindowOverflow];'
    if s.count(old_call)!=1:
        raise ValueError("V100 old overflow owner selector drift")
    s=s.replace(old_call,'NSLog(@"[SCARLET_V100_MORPH] legacy_hold_not_installed=1");',1)
    s=s.replace(method_anchor,WINDOW_METHOD+method_anchor,1)
    s=s.replace('overflow.accessibilityHint = @"Tap for window options. Hold to switch guests. Drag to move.";',
                'overflow.accessibilityHint = @"Tap to expand recent guest apps. Hold for window actions. Drag to move.";',1)
    return s

def apply(root: Path):
    files=(root/DOCK,root/WINDOW)
    if any(not p.is_file() or p.is_symlink() for p in files):
        raise ValueError("expected regular pinned source files")
    old=[p.read_text(encoding="utf-8") for p in files]
    updated=[patch_dock(old[0]),patch_window(old[1])]
    if any(fn(value)!=value for fn,value in zip((patch_dock,patch_window),updated)):
        raise ValueError("V100 not idempotent")
    for p, before, after in zip(files,old,updated):
        if before!=after:p.write_text(after,encoding="utf-8")
    print("[PASS] V100 single-origin morph, outside collapse, trigger hidden, long-hold native menu")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v100_morph_guest_switcher.py <LiveContainer source>")
    apply(Path(sys.argv[1]))
