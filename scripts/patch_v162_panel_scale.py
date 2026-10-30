#!/usr/bin/env python3
"""V162: make one shared native glass picker about one-sixth smaller.
Preserve actual button hit targets, fonts, tab geometry, window gesture routing.
"""
from pathlib import Path
import sys
DOCK=Path('MultitaskSupport/MultitaskDockView.swift')
MARK='SCARLET_V162_SIXTH_SMALLER'

def one(source, old, new, name):
    count=source.count(old)
    if count!=1:raise ValueError(f'V162 {name} source anchor drift: {count}')
    return source.replace(old,new,1)

def patch(source):
    if MARK in source:
        for marker in ('SCARLET_V162_COMPACT_VERTICAL','SCARLET_V162_HIDE_REDUNDANT_FOOTER'):
            if marker not in source:raise ValueError('V162 incomplete patch: '+marker)
        if source.count(MARK + ':')!=1:raise ValueError('V162 duplicate geometry marker')
        return source
    for marker in ('SCARLET_V161_RESIZE_TAB','SCARLET_V161_BLANK_PANEL_DISMISS',
                   'SCARLET_V160_GEOMETRY_PARITY','SCARLET_V160_GLASS_CONTRAST'):
        if marker not in source:raise ValueError('V162 requires V161: '+marker)
    # Width: adjust computed width by exactly 1/6, but preserve a 270pt
    # accessibility floor on narrow iPhones. Do not scale text or buttons.
    source=one(source,'''        let panelWidth = min(390, availableWidth)
        NSLog("[SCARLET_V157_WIDTH]''', '''        // SCARLET_V162_SIXTH_SMALLER: 5/6 of the V161 panel width,
        // with a safe floor for two tabs and Korean action button labels.
        let panelWidth = max(CGFloat(270), min(CGFloat(390), availableWidth) * (5.0 / 6.0))
        NSLog("[SCARLET_V162_SIXTH_SMALLER] panel=%.1f baseline=%.1f", panelWidth, min(CGFloat(390), availableWidth))
        NSLog("[SCARLET_V157_WIDTH]''','width')
    # Reduce vertical chrome, not the content rows or 47pt tap targets.
    source=one(source,'''        content.spacing = 9''', '''        // SCARLET_V162_COMPACT_VERTICAL: tighter chrome, unchanged controls.
        content.spacing = 7''','stack spacing')
    source=one(source,'''            content.topAnchor.constraint(equalTo: material.contentView.topAnchor, constant: 20),
            content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -18)''', '''            content.topAnchor.constraint(equalTo: material.contentView.topAnchor, constant: 16),
            content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -14)''','vertical padding')
    # A hint about outside tapping occupies a separate row and becomes
    # redundant with direct dismiss. Preserve its text for accessibility
    # logging/test contracts, just do not render another row in the panel.
    source=one(source,'''        content.addArrangedSubview(footer)

        // SCARLET_V126_INPLACE_TAB_CONTENT:''', '''        content.addArrangedSubview(footer)
        // SCARLET_V162_HIDE_REDUNDANT_FOOTER: compress the panel without
        // shrinking 42pt native tab and 47pt app/action touch surfaces.
        footer.isHidden = true

        // SCARLET_V126_INPLACE_TAB_CONTENT:''','footer')
    return source

def apply(root):
    path=root/DOCK
    if not path.is_file() or path.is_symlink():raise ValueError('V162 generated source unavailable')
    original=path.read_text(encoding='utf-8')
    updated=patch(original)
    if patch(updated)!=updated:raise ValueError('V162 non-idempotent')
    if updated!=original:path.write_text(updated,encoding='utf-8')
    print('[PASS] V162 picker scaled to 5/6; native buttons and dismissal preserved')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v162_panel_scale.py <LiveContainer>')
    apply(Path(sys.argv[1]))
