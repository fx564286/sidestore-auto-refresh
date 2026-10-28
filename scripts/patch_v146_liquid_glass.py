#!/usr/bin/env python3
"""V146: restore true native glass on panel, tabs, and EVERY row.
Preserve existing event targets, host ownership, closeWindow selector, JIT and signing.
"""
from pathlib import Path
import sys
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V146_COMPLETE_LIQUID_GLASS"

def one(s, old, new, reason):
    n=s.count(old)
    if n!=1:raise ValueError(f"V146 {reason}: {n} matches")
    return s.replace(old,new,1)

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or s.count("scarlet.v146.glass.action")!=3 or '("앱 닫기", "closeWindow")' not in s:
            raise ValueError("V146 partial overlay")
        return s
    for p in ("SCARLET_V145_NATIVE_GLASS_AND_DISMISS","SCARLET_V144_GLASS_INSTALLED",
              "SCARLET_V139_PANEL_TOUCH"):
        if p not in s:raise ValueError("V146 missing prerequisite: "+p)
    # V145 regular was opaque over live video. Use the actual native
    # interactive clear effect at the panel; independent controls get
    # dynamic native glass rather than translucent secondarySystemBackground.
    s=one(s,"let steadyGlass = UIGlassEffect(style: .regular)",
      '''// V146 clear native refraction at the
            // parent pane, no gray material replacing video with an opaque card.
            let steadyGlass = UIGlassEffect(style: .clear)''',"native panel clarity")
    s=one(s,'("창 닫기", "closeWindow")','("앱 닫기", "closeWindow")',"restore app-close label")
    s=one(s,'''            tabPicker.backgroundColor = UIColor.white.withAlphaComponent(0.12)
            tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.48)''',
    '''            // The original segmented control is still the sole tap owner.
            // The housing now has native iOS glass, not a milky white fill.
            let tabsGlassEffect = UIGlassEffect(style: .regular)
            tabsGlassEffect.isInteractive = true
            let tabsGlass = UIVisualEffectView(effect: tabsGlassEffect)
            tabsGlass.isUserInteractionEnabled = false
            tabsGlass.layer.cornerRadius = 20
            tabsGlass.layer.cornerCurve = .continuous
            tabsGlass.clipsToBounds = true
            tabsGlass.translatesAutoresizingMaskIntoConstraints = false
            tabHousing.insertSubview(tabsGlass, at: 0)
            NSLayoutConstraint.activate([
                tabsGlass.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor),
                tabsGlass.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor),
                tabsGlass.topAnchor.constraint(equalTo: tabHousing.topAnchor),
                tabsGlass.bottomAnchor.constraint(equalTo: tabHousing.bottomAnchor)
            ])
            tabPicker.backgroundColor = .clear
            tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.14)''',"tabs no longer tinted cards")
    needle='''                item.backgroundColor = UIColor.secondarySystemBackground.withAlphaComponent(0.56)
                item.layer.borderColor = UIColor.separator.withAlphaComponent(0.42).cgColor
                item.layer.borderWidth = 0.55
                item.layer.cornerCurve = .continuous'''
    if s.count(needle)!=2: raise ValueError(f"V146 direct/recent rows expected; observed={s.count(needle)}")
    replacement='''                item.backgroundColor = .clear
                item.layer.borderColor = UIColor.white.withAlphaComponent(0.29).cgColor
                item.layer.borderWidth = 0.55
                item.layer.cornerCurve = .continuous
                let actionGlassEffect = UIGlassEffect(style: .regular)
                actionGlassEffect.isInteractive = true
                let actionGlass = UIVisualEffectView(effect: actionGlassEffect)
                actionGlass.accessibilityIdentifier = "scarlet.v146.glass.action"
                actionGlass.isUserInteractionEnabled = false
                actionGlass.layer.cornerRadius = 15
                actionGlass.layer.cornerCurve = .continuous
                actionGlass.clipsToBounds = true
                actionGlass.translatesAutoresizingMaskIntoConstraints = false
                item.insertSubview(actionGlass, at: 0)
                NSLayoutConstraint.activate([
                    actionGlass.leadingAnchor.constraint(equalTo: item.leadingAnchor),
                    actionGlass.trailingAnchor.constraint(equalTo: item.trailingAnchor),
                    actionGlass.topAnchor.constraint(equalTo: item.topAnchor),
                    actionGlass.bottomAnchor.constraint(equalTo: item.bottomAnchor)
                ])'''
    s=s.replace(needle,replacement)
    deep_needle="\n".join("    "+line for line in needle.split("\n"))
    deep_replacement="\n".join("    "+line for line in replacement.split("\n"))
    s=one(s,deep_needle,deep_replacement,"window action glass")
    # 3 occurrences in the resulting Swift; the marker in this script is
    # single at the beginning of main panel, not each row.
    s=one(s,'NSLog("[SCARLET_V144_GLASS_INSTALLED] lens=native_clear border=continuous")',
         'NSLog("[SCARLET_V144_GLASS_INSTALLED] lens=native_clear border=continuous")\n        NSLog("[SCARLET_V146_COMPLETE_LIQUID_GLASS] panel=native_clear tabs=native rows=native")',
         "single runtime evidence marker")
    return s

def apply(root):
    p=root/DOCK
    if not p.is_file() or p.is_symlink():raise ValueError("V146 pinned dock missing")
    old=p.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:raise ValueError("V146 patch not idempotent")
    if old!=new:p.write_text(new,encoding="utf-8")
    print("[PASS] V146 native glass panel/tabs/all three row types + restore app-close label")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v146_liquid_glass.py <LiveContainer>")
    apply(Path(sys.argv[1]))
