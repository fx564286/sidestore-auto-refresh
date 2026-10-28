#!/usr/bin/env python3
"""V148: native Liquid Glass belongs to each window-action UIButton.

Applied on top of the verified V147 build, never by stacking another
UIVisualEffectView behind a plain button. Keeps existing selectors and the
single host-owned dismiss gesture. No new App ID, UIWindow, or guest runtime.
"""
from pathlib import Path
import sys

FILE = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "SCARLET_V148_ACTION_GLASS_NATIVE_OWNER"

def patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or source.count('config = UIButton.Configuration.glass()') != 1:
            raise ValueError("V148 incomplete or duplicate button glass")
        return source
    required = (
        "SCARLET_V147_WINDOW_ACTION_NATIVE_GLASS",
        "SCARLET_V147_FROM_V144_GLASS_OWNER",
        "SCARLET_V147_DIRECT_HOST_ROUTING" # host route is in SwiftUI, not dock
    )
    for marker in required[:2]:
        if marker not in source:
            raise ValueError("V148 missing V147 source " + marker)

    start = source.index("            // SCARLET_V147_WINDOW_ACTION_NATIVE_GLASS:")
    end = source.index("                item.heightAnchor.constraint(equalToConstant: 47).isActive = true", start)
    segment = source[start:end]
    expected = '''                item.layer.cornerRadius = 15
                if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
                    item.configuration = .glass()
                    NSLog("[SCARLET_V147_ACTION_GLASS] button=%@", selectorName)
                    item.backgroundColor = .clear
                    item.layer.borderColor = UIColor.white.withAlphaComponent(0.25).cgColor
                    item.layer.borderWidth = 0.5
                    item.layer.cornerCurve = .continuous
                    // Native Liquid Glass is owned by UIButton.Configuration.glass()
                    // and responds to touch; do NOT put a separate static
                    // UIVisualEffectView behind a plain UIButton.
                } else {
                    item.backgroundColor = UIColor.secondarySystemGroupedBackground
                }
                item.setTitle(title, for: .normal)
                item.setTitleColor(.label, for: .normal)
'''
    if segment.count(expected) != 1:
        raise ValueError("V148 target window-action UIButton style mismatch")
    new = '''                // SCARLET_V148_ACTION_GLASS_NATIVE_OWNER: the ACTION
                // CONTROL itself owns an interactive Liquid Glass style.
                // Do not paint secondarySystemBackground, a white border, or
                // any extra effectView over the native button surface.
                item.accessibilityIdentifier = "scarlet.v148.windowaction." + selectorName
                item.accessibilityLabel = title
                if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
                    var config = UIButton.Configuration.glass()
                    config.title = title
                    config.baseForegroundColor = UIColor.label
                    config.cornerStyle = .large
                    item.configuration = config
                    NSLog("[SCARLET_V147_ACTION_GLASS] button=%@", selectorName)
                    NSLog("[SCARLET_V148_ACTION_GLASS] action=%@ owner=UIButton style=glass", selectorName)
                } else {
                    // Accessibility fallback, not the default iOS 26+ path.
                    item.configuration = .plain()
                    item.backgroundColor = UIColor.secondarySystemGroupedBackground
                    item.setTitle(title, for: .normal)
                    item.setTitleColor(.label, for: .normal)
                }
'''
    source=source[:start]+segment.replace(expected,new,1)+source[end:]
    if '("창 닫기", "closeWindow")' in source:
        raise ValueError("V148 UI still contains obsolete panel close label")
    if '("앱 닫기", "closeWindow")' not in source:
        raise ValueError("V148 lost genuine guest app close action")
    for marker in ("SCARLET_V141_OUTSIDE_TAP_DISMISS",
                   "outsideObserver.install(with: outsideTap)",
                   "바깥을 누르면 창 관리 닫기"):
        if marker not in source:
            raise ValueError("V148 outside dismiss contract missing "+marker)
    return source

def apply(root: Path) -> None:
    path=root/FILE
    if not path.is_file() or path.is_symlink():
        raise ValueError("V148 cannot locate canonical V147 picker")
    old=path.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:
        raise ValueError("V148 patch not idempotent")
    if old!=new:path.write_text(new,encoding="utf-8")
    print("[PASS] V148 right-tab action buttons native glass, app close semantics and outside tap")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v148_action_glass.py <LiveContainer>")
    apply(Path(sys.argv[1]))
