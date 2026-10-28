#!/usr/bin/env python3
"""Keep floating guest windows within the visible stage."""
from pathlib import Path
import sys

SOURCE=Path('MultitaskSupport/DecoratedAppSceneViewController.m')
MARK='SCARLET_V143_NO_EDGE_PEEK'

def patch(source):
    if MARK in source:
        if source.count(MARK)!=1:
            raise ValueError('V143 duplicate frame repair')
        return source
    if 'SCARLET_V141_INSET_AWARE_SETTLE' not in source:
        raise ValueError('V143 requires V141 geometry')
    old='''    CGFloat oobOffset = MAX(30, frame.size.width - 30);
    frame.origin.x = MAX(maxFrame.origin.x - oobOffset, MIN(CGRectGetMaxX(maxFrame) - frame.size.width + oobOffset, center.x - frame.size.width / 2));'''
    new='''    // SCARLET_V143_NO_EDGE_PEEK: no ~30pt edge sliver.
    CGFloat minX = CGRectGetMinX(maxFrame);
    CGFloat maxX = MAX(minX, CGRectGetMaxX(maxFrame) - frame.size.width);
    frame.origin.x = MAX(minX, MIN(maxX, center.x - frame.size.width / 2));'''
    if source.count(old)!=1:
        raise ValueError('V143 windowed frame source mismatch')
    source=source.replace(old,new,1)
    # An interrupted minimize previously left the guest partially visible.
    old_close='''    } completion:^(BOOL finished) {
        if (!finished) return;
        self.view.hidden = YES;
        self.view.transform = CGAffineTransformIdentity;
        [self.view.superview sendSubviewToBack:self.view];
    }];
}

- (void)minimizeWindowPiP'''
    new_close='''    } completion:^(BOOL finished) {
        // SCARLET_V143_INTERRUPTED_MINIMIZE: dismiss a fading guest after
        // interrupted rotation, but do not hide an opaque reactivated scene.
        if (!finished && self.view.alpha >= 0.95) return;
        self.view.hidden = YES;
        self.view.alpha = 1.0;
        self.view.transform = CGAffineTransformIdentity;
        [self.view.superview sendSubviewToBack:self.view];
    }];
}

- (void)minimizeWindowPiP'''
    if source.count(old_close)!=1:
        raise ValueError('V143 minimize completion source mismatch')
    return source.replace(old_close,new_close,1)

def apply(root):
    path=root/SOURCE
    if not path.is_file() or path.is_symlink():
        raise ValueError('missing source')
    old=path.read_text()
    new=patch(old)
    if patch(new)!=new:
        raise ValueError('not idempotent')
    if old!=new:path.write_text(new)
    print('[PASS] V143 floating guest stays inside viewport')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v143_guest_window_peek.py <source>')
    apply(Path(sys.argv[1]))
