#!/usr/bin/env python3
"""V160: one geometry grid, perceptible glass on white backgrounds, deterministic outside dismissal.

Patch only V159's generated LiveContainer Swift; do not create new windows, controls,
or runtime modes. Every transformation is one-anchor and idempotent.
"""
from pathlib import Path
import sys
import re

DOCK = Path('MultitaskSupport/MultitaskDockView.swift')
MARK = 'SCARLET_V160_OUTSIDE_RETURN'


def one(src, before, after, label):
    count = src.count(before)
    if count != 1:
        raise ValueError(f'V160 {label} anchor drift: {count}')
    return src.replace(before, after, 1)


def patch(src):
    if MARK in src:
        for required in ('SCARLET_V160_GEOMETRY_PARITY', 'SCARLET_V160_GLASS_CONTRAST',
                         'SCARLET_V160_GUEST_WINDOW_COORDS', 'SCARLET_V160_BUTTON_RIM'):
            if required not in src:
                raise ValueError('V160 partial patch: ' + required)
        if src.count(MARK + ':') != 1:
            raise ValueError('V160 duplicate patch')
        return src
    for required in ('SCARLET_V159_PINNED_OUTER_FRAME', 'SCARLET_V159_ACTION_NATIVE_PRESS',
                     'SCARLET_V158_EQUAL_ROW_GEOMETRY', 'SCARLET_V156_OUTSIDE_TOUCH_TRACE'):
        if required not in src:
            raise ValueError('V160 missing prerequisite: ' + required)

    # A UIKit overlay must own outside hits even when its child glass panel
    # has an animated transform. No second recognizer or UIWindow is created.
    src = one(src, '''        if let panel = activePanel, !panel.frame.contains(point) {
            return self
        }
        return super.hitTest(point, with: event)''', '''        if let panel = activePanel,
           !panel.convert(panel.bounds, to: self).contains(point) {
            return self
        }
        return super.hitTest(point, with: event)''', 'backdrop transformed hit-test')
    src = one(src, '''                    self.dismissOutside?()
                }
            }
        }
        super.touchesBegan(touches, with: event)''', '''                    self.dismissOutside?()
                }
                // SCARLET_V160_OUTSIDE_RETURN: do not hand an outside
                // finger-down back to UIControl or the guest after dismissal.
                // UIKit removal remains deferred to the next main run loop.
                NSLog("[SCARLET_V160_OUTSIDE_RETURN] phase=outside_down")
                return
            }
        }
        super.touchesBegan(touches, with: event)''', 'outside event early return')

    # In LiveProcess, owner may no longer equal the current panel.window.
    # Evaluate touches against the panel's *actual* UIWindow, not a stale
    # captured owner; compare both points in the same UIScreen space.
    src = one(src, '''        guard let owner, let panel, panel.window === owner else { return }
        let windows = UIApplication.shared.connectedScenes.compactMap {''', '''        guard let owner, let panel,
              let panelWindow = panel.window,
              panelWindow.screen === owner.screen else { return }
        let windows = UIApplication.shared.connectedScenes.compactMap {''', 'observer refresh guard')
    src = one(src, '''        guard let owner, let panel, panel.window === owner,
              let window = touch.window,
              window.screen === owner.screen else { return false }
        // Normalize both windows to screen coordinates. The prior
        // touch.location(in: panel) across different guest scenes could
        // misclassify an outside touch as inside.
        let onScreen = window.convert(touch.location(in: window), to: owner.screen.coordinateSpace)
        let panelOnScreen = owner.convert(panel.convert(panel.bounds, to: owner), to: owner.screen.coordinateSpace)
        return !panelOnScreen.contains(onScreen)''', '''        guard let panel, let panelWindow = panel.window,
              let window = touch.window,
              window.screen === panelWindow.screen else { return false }
        // SCARLET_V160_GUEST_WINDOW_COORDS: UIKit's scene/window ownership
        // may change between presentation and the touch. Use the actual
        // panel window and screen-space conversion for both points.
        let screenSpace = panelWindow.screen.coordinateSpace
        let onScreen = window.convert(touch.location(in: window), to: screenSpace)
        let panelOnScreen = panelWindow.convert(
            panel.convert(panel.bounds, to: panelWindow), to: screenSpace)
        let outside = !panelOnScreen.contains(onScreen)
        NSLog("[SCARLET_V160_GUEST_WINDOW_COORDS] outside=%d", outside ? 1 : 0)
        return outside''', 'window-local outside classification')
    src = one(src, '''              owner != nil, panel?.window === owner else { return }
        dismissQueued = true''', '''              panel?.window != nil else { return }
        dismissQueued = true''', 'guest-window callback eligibility')

    # Keep the ACTION-row 18pt optical clearance needed for long presses.
    # Match the top tabs to that effective content width, not vice versa.
    src = one(src, '''            tabPicker.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor),
            tabPicker.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor),''', '''            // SCARLET_V160_GEOMETRY_PARITY: match the rows' 18pt insets.
            tabPicker.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18),
            tabPicker.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor, constant: -18),''', 'segment geometry')
    src = one(src, '''                tabRim.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor),
                tabRim.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor),''', '''                tabRim.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor, constant: 18),
                tabRim.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor, constant: -18),''', 'tab rim geometry')

    # Native clear glass stays interactive. A subtle dynamic tint in the
    # existing UIVisualEffectView content and neutral separator border keep
    # white backgrounds readable without painting an opaque replacement.
    src = one(src, '''        material.layer.borderWidth = 1.0
        material.layer.borderColor = UIColor.white.withAlphaComponent(0.62).cgColor''', '''        // SCARLET_V160_GLASS_CONTRAST: neutral edge against white or black.
        material.layer.borderWidth = 1.0
        material.layer.borderColor = UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor.white.withAlphaComponent(0.34)
                : UIColor.black.withAlphaComponent(0.19)
        }.cgColor
        material.contentView.backgroundColor = UIColor.secondarySystemBackground.withAlphaComponent(0.16)
        NSLog("[SCARLET_V160_GLASS_CONTRAST] mode=adaptive")''', 'light/dark surface separation')
    src = one(src, '''            tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.18)''', '''            tabPicker.selectedSegmentTintColor = UIColor.tertiarySystemFill''', 'native selected tab contrast')

    # Single native button type is kept; a 0.6pt optical border clarifies
    # the controls on pure-white guests. Do not alter intrinsic height/width.
    rim_anchor = r'(?m)^( +)item\.heightAnchor\.constraint\(equalToConstant: 47\)\.isActive = true$'
    if len(re.findall(rim_anchor, src)) != 2:
        raise ValueError('V160 row optical border anchor drift: ' + str(len(re.findall(rim_anchor, src))))
    def with_rim(match):
        spaces = match.group(1)
        return '\n'.join(spaces + line for line in (
            '// SCARLET_V160_BUTTON_RIM: readable native glass on light guests.',
            'item.layer.cornerRadius = 23.5',
            'item.layer.cornerCurve = .continuous',
            'item.layer.borderWidth = 0.6',
            'item.layer.borderColor = UIColor.separator.cgColor',
            'item.heightAnchor.constraint(equalToConstant: 47).isActive = true',
        ))
    src = re.sub(rim_anchor, with_rim, src)
    return src


def apply(root):
    path = root / DOCK
    if not path.is_file() or path.is_symlink():
        raise ValueError('V160 source not available')
    original = path.read_text(encoding='utf-8')
    result = patch(original)
    if patch(result) != result:
        raise ValueError('V160 non-idempotent')
    if result != original:
        path.write_text(result, encoding='utf-8')
    print('[PASS] V160 outside dismissal / same-width native glass / light-background contrast')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: patch_v160_outside_visual_parity.py <LiveContainer>')
    apply(Path(sys.argv[1]))
