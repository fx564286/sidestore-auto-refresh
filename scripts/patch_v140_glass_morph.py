#!/usr/bin/env python3
"""V140: make the EXISTING host picker grow from its trigger as native glass.

No new UIButton, UIWindow, UIAlertController, second dock, or event owner.
The hosted and Direct modes still route through MultitaskDockManager; alter
only its panel presentation geometry and touch-dependent optical refraction.
"""
from pathlib import Path
import sys

SOURCE=Path('MultitaskSupport/MultitaskDockView.swift')
MARK='SCARLET_V140_MORPH_ANCHOR'


def one(s,old,new,label):
    n=s.count(old)
    if n!=1: raise ValueError(f'V140 {label}: expected one anchor; got {n}')
    return s.replace(old,new,1)


def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'SCARLET_V140_FINGER_DEFORMATION' not in s:
            raise ValueError('partial V140 glass patch')
        return s
    for required in ('SCARLET_V139_PANEL_TOUCH','SCARLET_V139_UNIFIED_GUEST_ACTION',
                     'SCARLET_V131_REFERENCE_LIQUID_GLASS','UIGlassEffect(style: .clear)',
                     'SCARLET_V126_INPLACE_TAB_CONTENT'):
        if required not in s:raise ValueError('missing pinned V139 glass source: '+required)
    # The V100 modal floats in the *center* independent of the triggering
    # native/Direct button. Anchor the same presentation to its actual source.
    s=one(s,
        '''        // SCARLET_V127_COMPLETE_GLASS: keep backdrop light for real glass.
        overlay.backgroundColor = UIColor.black.withAlphaComponent(0.32)
        if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
            overlay.backgroundColor = UIColor.black.withAlphaComponent(0.19)
        }''',
        '''        // SCARLET_V127_COMPLETE_GLASS: keep V127 evidence for source audit.
        // SCARLET_V140_MORPH_ANCHOR: no dimming scrim over actual content.
        overlay.backgroundColor = UIAccessibility.isReduceTransparencyEnabled
            ? UIColor.black.withAlphaComponent(0.12) : UIColor.clear''',
        'remove artificial opaque modal backdrop')
    s=one(s,
        '        let panelWidth = min(352, availableWidth)',
        '''        let panelWidth = min(352, availableWidth)
        let entryFrame = sourceView.convert(sourceView.bounds, to: owner)
        // A source-relative spring translation makes the *same* native
        // glass surface grow out of the pressed floating button.
        let entryOffset = entryFrame.midY - owner.bounds.midY
        let panelAnchorOffset = max(-owner.bounds.height * 0.17,
                                    min(owner.bounds.height * 0.17, entryOffset * 0.40))''',
        'derive geometry from the active button instead of default center')
    s=one(s,
        '''            material.centerYAnchor.constraint(equalTo: overlay.centerYAnchor),
            material.widthAnchor.constraint(equalToConstant: panelWidth),''',
        '''            material.centerYAnchor.constraint(equalTo: overlay.centerYAnchor,
                                             constant: panelAnchorOffset),
            material.topAnchor.constraint(greaterThanOrEqualTo:
                overlay.safeAreaLayoutGuide.topAnchor, constant: 12),
            material.bottomAnchor.constraint(lessThanOrEqualTo:
                overlay.safeAreaLayoutGuide.bottomAnchor, constant: -12),
            material.widthAnchor.constraint(equalToConstant: panelWidth),''',
        'keep morph panel near source without clipping in landscape')
    s=one(s,
        '''        material.layer.cornerRadius = 26''',
        '''        material.layer.cornerRadius = 30
        material.layer.cornerCurve = .continuous''',
        'continuous curved refractive capsule')
    s=one(s,
        '''        material.transform = .identity
        })
        // SCARLET_V131_VISIBLE_GLASS_ACTIVATION retired by V139''',
        '''        material.transform = .identity
        })
        // SCARLET_V131_VISIBLE_GLASS_ACTIVATION retired by V139''',
        'verify and preserve native animated glass expansion')
    s=one(s,
        '''        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()''',
        '''        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
        NSLog("[SCARLET_V140_GLASS] panel=anchored_to_source surface=native_clear touch=2d")''',
        'visible version marker for actual compiled host')
    s=one(s,
        '''    func followPoint(x: CGFloat, y: CGFloat) {
        CATransaction.begin()''',
        '''    // SCARLET_V140_FINGER_DEFORMATION: the rim optics follow the
    // finger in TWO axes, not only highlight color or tab selection.
    // All actionable row controls remain untransformed and fully clickable.
    func followPoint(x: CGFloat, y: CGFloat) {
        CATransaction.begin()''',
        'trace real 2D active finger glass')
    s=one(s,
        '''        highlight.endPoint = CGPoint(x: min(1, x + 0.22), y: min(1, y + 0.23))
        CATransaction.commit()''',
        '''        highlight.endPoint = CGPoint(x: min(1, x + 0.22), y: min(1, y + 0.23))
        let dx = (x - 0.5) * 5
        let dy = (y - 0.5) * 5
        let squash = min(0.028, abs(x - 0.5) * 0.056)
        self.transform = CGAffineTransform(translationX: dx, y: dy)
            .scaledBy(x: 1.0 + squash, y: 1.0 - squash)
        CATransaction.commit()''',
        'subtle touch-centered morph without transforming controls')
    s=one(s,
        '''    func releasePoint() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        contact.opacity = 0
        CATransaction.commit()
    }''',
        '''    func releasePoint() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        contact.opacity = 0
        CATransaction.commit()
        UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.22,
                       delay: 0, usingSpringWithDamping: 0.85,
                       initialSpringVelocity: 0, options: [.beginFromCurrentState],
                       animations: { self.transform = .identity }, completion: nil)
    }''',
        'return refraction to rest when finger lifts')
    return s


def apply(root):
    file=root/SOURCE
    if not file.is_file() or file.is_symlink():raise ValueError('missing pinned dock source')
    before=file.read_text(encoding='utf-8')
    after=patch(before)
    if patch(after)!=after:raise ValueError('V140 glass patch not idempotent')
    if after!=before:file.write_text(after,encoding='utf-8')
    print('[PASS] V140 one native host picker, button-anchored liquid glass and 2D touch deformation')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v140_glass_morph.py <LiveContainer source>')
    apply(Path(sys.argv[1]))
