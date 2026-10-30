#!/usr/bin/env python3
"""V163 enlarge native tab/action/recent buttons, preserve V162 panel geometry.

The panel's fixed width and scroll viewport remain unchanged. Increase the
button footprint inside it by reducing *content* side padding only; retain the
18pt optical press clearance between native glass and its scroll boundary.
"""
from pathlib import Path
import sys

DOCK = Path('MultitaskSupport/MultitaskDockView.swift')
MARK = 'SCARLET_V163_BUTTON_FOOTPRINT'


def one(src, before, after, label):
    count = src.count(before)
    if count != 1:
        raise ValueError(f'V163 {label} anchor drift: {count}')
    return src.replace(before, after, 1)


def patch(src):
    if MARK in src:
        for required in ('SCARLET_V163_PRESS_CLEARANCE',
                         'SCARLET_V163_NATIVE_HEIGHT'):
            if required not in src:
                raise ValueError('V163 incomplete patch: '+required)
        if src.count('['+MARK+']') != 1:
            raise ValueError('V163 duplicate version marker')
        return src
    for marker in ('SCARLET_V162_SIXTH_SMALLER', 'SCARLET_V161_BLANK_PANEL_DISMISS',
                   'SCARLET_V159_ACTION_NATIVE_PRESS', 'SCARLET_V160_GEOMETRY_PARITY'):
        if marker not in src:
            raise ValueError('V163 requires V162: '+marker)

    # +14pt total tab and action width; no change to panelWidth or glass size.
    src = one(src, '''            content.leadingAnchor.constraint(equalTo: material.contentView.leadingAnchor, constant: 17),
            content.trailingAnchor.constraint(equalTo: material.contentView.trailingAnchor, constant: -17),''', '''            // SCARLET_V163_BUTTON_FOOTPRINT: +14pt within the exact V162
            // outer panel frame. Keep the glass rim and inset row grid aligned.
            content.leadingAnchor.constraint(equalTo: material.contentView.leadingAnchor, constant: 10),
            content.trailingAnchor.constraint(equalTo: material.contentView.trailingAnchor, constant: -10),''', 'common content width')

    src = one(src, '''            content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -14)
        ])

        let heading = UILabel()''', '''            content.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor, constant: -14)
        ])
        NSLog("[SCARLET_V163_BUTTON_FOOTPRINT] width_delta=14 native_only=1")

        let heading = UILabel()''', 'V163 diagnostic outside constraint array')

    # Preserving the existing 18pt optical clearance prevents clipped bloom.
    # In addition, do NOT add transforms/scaling on long press; use Apple's
    # native clearGlass press on the same UIButton used before.
    if src.count('rows.layoutMargins = UIEdgeInsets(top: 0, left: 18, bottom: 0, right: 18)') != 2:
        raise ValueError('V163 row optical clearance changed')
    src = one(src, '''            // SCARLET_V158_EQUAL_ROW_GEOMETRY: same button geometry in both tabs.
            rows.layoutMargins''', '''            // SCARLET_V163_PRESS_CLEARANCE: retain 18pt native bloom space,
            // unchanged scroll.clipsToBounds=false and no additional transform.
            // SCARLET_V158_EQUAL_ROW_GEOMETRY: same button geometry in both tabs.
            rows.layoutMargins''', 'native long-press clearance')

    before = 'item.heightAnchor.constraint(equalToConstant: 47).isActive = true'
    if src.count(before) != 2:
        raise ValueError('V163 button height anchor drift: '+str(src.count(before)))
    src = src.replace(before, 'item.heightAnchor.constraint(equalToConstant: 48).isActive = true')
    # Two 48pt buttons within 54pt recent row, three 48pt actions with 7pt
    # gaps fit the existing 162pt scroll viewport: 3*48+2*7 = 158pt.
    before = 'item.layer.cornerRadius = 23.5\n            item.layer.cornerCurve = .continuous\n            item.layer.borderWidth = 0.6'
    if src.count(before) != 1:
        raise ValueError('V163 recent native corner radius anchor drift: '+str(src.count(before)))
    src = src.replace(before, before.replace('23.5', '24'), 1)
    before = 'item.layer.cornerRadius = 23.5\n                item.layer.cornerCurve = .continuous\n                item.layer.borderWidth = 0.6'
    if src.count(before) != 1:
        raise ValueError('V163 action native corner radius anchor drift: '+str(src.count(before)))
    src = src.replace(before, before.replace('23.5', '24'), 1)
    src = one(src, '''                // SCARLET_V158_ACTION_UNCLIPPED: native clearGlass has
                // 18pt horizontal optical clearance and no scroll clipping.''', '''                // SCARLET_V163_NATIVE_HEIGHT: 48pt vs V162 47pt, fits 162pt
                // action viewport with 7pt spacing; no custom press scale.
                // SCARLET_V158_ACTION_UNCLIPPED: native clearGlass has
                // 18pt horizontal optical clearance and no scroll clipping.''', 'native action touch and optical height')
    return src


def apply(root):
    path = root / DOCK
    if not path.is_file() or path.is_symlink():
        raise ValueError('V163 Swift source not present')
    original = path.read_text(encoding='utf-8')
    updated = patch(original)
    if patch(updated) != updated:
        raise ValueError('V163 patch is not idempotent')
    if updated != original:
        path.write_text(updated, encoding='utf-8')
    print('[PASS] V163 wider/taller native buttons; V162 outer panel untouched')

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: patch_v163_button_size_native.py <LC>')
    apply(Path(sys.argv[1]))
