#!/usr/bin/env python3
"""V161: compact variable-height picker, preserve one native panel; tap blank glass closes.
Run after V160; no extra UIWindow or gesture recognizer, no Direct code.
"""
from pathlib import Path
import sys
DOCK = Path('MultitaskSupport/MultitaskDockView.swift')
MARK = 'SCARLET_V161_BLANK_PANEL_DISMISS'

def one(s, old, new, detail):
    n=s.count(old)
    if n != 1:
        raise ValueError(f'V161 {detail} anchor drift: {n}')
    return s.replace(old,new,1)

def patch(src):
    if MARK in src:
        for label in ('SCARLET_V161_ADAPTIVE_LIST_HEIGHT', 'SCARLET_V161_RESIZE_TAB',
                      'SCARLET_V161_WINDOW_RECEIVER'):
            if label not in src:raise ValueError('V161 partial patch: '+label)
        if src.count('SCARLET_V161_BLANK_PANEL_DISMISS') != 2:
            raise ValueError('V161 duplicate blank dismissal')
        return src
    for label in ('SCARLET_V160_OUTSIDE_RETURN','SCARLET_V160_GLASS_CONTRAST',
                  'SCARLET_V159_PINNED_OUTER_FRAME','SCARLET_V158_EQUAL_TAB_FRAME'):
        if label not in src:raise ValueError('V161 missing V160 prerequisite: '+label)

    src=one(src, '''        return !panelOnScreen.contains(onScreen)
    }

    func gestureRecognizer(_ recognizer: UIGestureRecognizer,''', '''        if !panelOnScreen.contains(onScreen) { return true }
        // SCARLET_V161_BLANK_PANEL_DISMISS: an empty portion *inside*
        // the large native glass is a dismissal surface, not a dead zone.
        // Preserve real controls, long-presses and scrollable lists.
        var current: UIView? = touch.view
        while let view = current {
            if view === panel { break }
            if view is UIControl { return false }
            if let list = view as? UIScrollView,
               list.contentSize.height > list.bounds.height + 1 { return false }
            current = view.superview
        }
        NSLog("[SCARLET_V161_BLANK_PANEL_DISMISS] phase=blank_accepted")
        return true
    }

    func gestureRecognizer(_ recognizer: UIGestureRecognizer,''', 'blank area classifier')

    # This control may receive a finger-down directly (no gesture callback).
    # Its outside predicate also uses transformed geometry, not frame coords.
    src=one(src, '''            let outside = !panel.frame.contains(touch.location(in: self))
            NSLog("[SCARLET_V154_OUTSIDE]''', '''            let outside = !panel.convert(panel.bounds, to: self).contains(touch.location(in: self))
            NSLog("[SCARLET_V154_OUTSIDE]''', 'backdrop touch coordinate parity')

    # The guest UIWindow may become front-most after a scene migration.
    # The already-installed observer covers the newly foreground window on
    # scene activation as well as didBecomeKey and didBecomeVisible.
    src=one(src, '''        for name in [UIWindow.didBecomeVisibleNotification,
                     UIWindow.didBecomeKeyNotification] {''', '''        // SCARLET_V161_WINDOW_RECEIVER: refresh when a guest scene activates.
        for name in [UIWindow.didBecomeVisibleNotification,
                     UIWindow.didBecomeKeyNotification,
                     UIScene.didActivateNotification] {''', 'window event trace')
    src=one(src, '''                guard let self, let window = note.object as? UIWindow,
                      let owner = self.owner,
                      window.screen === owner.screen else { return }
                self.refreshWindows()''', '''                guard let self, let owner = self.owner else { return }
                if let window = note.object as? UIWindow {
                    guard window.screen === owner.screen else { return }
                } else if let scene = note.object as? UIWindowScene {
                    guard scene.screen === owner.screen else { return }
                } else { return }
                self.refreshWindows()''', 'window and scene change observer')
    # No duplicate recognizer creation. Instead refresh in the existing
    # gesture callback before filtering its touches by panel bounds.

    # V159 deliberately froze the tall 3-action list even when one guest
    # was present. Keep maximum 3 rows as a bounded scroll viewport; make
    # panel height follow active tab. This replaces fixed cross-tab height.
    src=one(src, '''        let listHeight = min(CGFloat(actionsCount * 54), maxListHeight)
        NSLog("[SCARLET_V158_FRAME_HEIGHT]''', '''        // SCARLET_V161_ADAPTIVE_LIST_HEIGHT: 1 recent guest = 1 row,
        // 3 action buttons = 3 rows; long recent lists scroll in 3 rows.
        let listHeight = min(CGFloat((windowActions ? actionsCount :
            max(1, min(3, recent.count))) * 54), maxListHeight)
        NSLog("[SCARLET_V158_FRAME_HEIGHT]''', 'initial compact viewport')
    src=one(src, '''            tabListHeightConstraint.constant = listHeight
            // SCARLET_V158_ROW_VERTICAL_PARITY:''', '''            tabListHeightConstraint.constant = min(
                CGFloat((windowActions ? actionsCount :
                    max(1, min(3, recent.count))) * 54), maxListHeight)
            // SCARLET_V158_ROW_VERTICAL_PARITY:''', 'active tab viewport height')
    src=one(src, '''        var stablePanelHeight: CGFloat = 0
        tabPicker.addAction(UIAction''', '''        var stablePanelHeight: CGFloat = 0
        var frozenHeight: NSLayoutConstraint?
        tabPicker.addAction(UIAction''', 'mutable constraint declaration')
    src=one(src, '''            windowActions = targetWindowActions
            // Never call collapse or present another controller on tab change.''', '''            windowActions = targetWindowActions
            // SCARLET_V161_RESIZE_TAB: use the same panel and controls,
            // but do not reserve two invisible rows for a single recent app.
            let nextListHeight = min(CGFloat((windowActions ? actionsCount :
                max(1, min(3, recent.count))) * 54), maxListHeight)
            frozenHeight?.constant = stablePanelHeight - listHeight + nextListHeight
            NSLog("[SCARLET_V161_RESIZE_TAB] list=%.1f panel=%.1f",
                  nextListHeight, frozenHeight?.constant ?? 0)
            // Never call collapse or present another controller on tab change.''', 'tab frame adjusts')
    src=one(src, '''            if abs(material.bounds.height - stablePanelHeight) > 0.5 {
                NSLog("[SCARLET_V159_PANEL_EQUAL] unexpected_layout_drift=%.2f",
                      material.bounds.height - stablePanelHeight)
                overlay.layoutIfNeeded()
            }''', '''            let targetHeight = stablePanelHeight - listHeight + nextListHeight
            if abs(material.bounds.height - targetHeight) > 0.5 {
                NSLog("[SCARLET_V161_RESIZE_TAB] settling=%.2f",
                      material.bounds.height - targetHeight)
                overlay.layoutIfNeeded()
            }''', 'adaptive height validation')
    src=one(src, '''        let frozenHeight = material.heightAnchor.constraint(equalToConstant: stablePanelHeight)
        frozenHeight.priority = .required
        frozenHeight.isActive = true''', '''        frozenHeight = material.heightAnchor.constraint(equalToConstant: stablePanelHeight)
        frozenHeight?.priority = .required
        frozenHeight?.isActive = true''', 'existing height constraint reused')
    return src

def apply(root):
    p=root/DOCK
    if not p.is_file() or p.is_symlink():raise ValueError('V161 generated Swift source missing')
    a=p.read_text(encoding='utf-8')
    b=patch(a)
    if patch(b)!=b: raise ValueError('V161 not idempotent')
    if a!=b:p.write_text(b,encoding='utf-8')
    print('[PASS] V161 dynamic list height and blank/outside touch routing')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v161_compact_outside.py <LC>')
    apply(Path(sys.argv[1]))
