#!/usr/bin/env python3
"""Keep floating guest windows within the visible stage."""
from pathlib import Path
import sys

SOURCE=Path('MultitaskSupport/DecoratedAppSceneViewController.m')
MARK='SCARLET_V143_NO_EDGE_PEEK'

def patch(source):
    if MARK in source:
        if source.count(MARK)!=1 or 'SCARLET_V143_INTERRUPTED_MINIMIZE' not in source:
            raise ValueError('V143 duplicate frame repair')
        return source
    if 'SCARLET_V141_INSET_AWARE_SETTLE' not in source:
        raise ValueError('V143 requires V141 geometry')
    old='''    CGFloat oobOffset = MAX(30, frame.size.width - 30);
    frame.origin.x = MAX(maxFrame.origin.x - oobOffset, MIN(CGRectGetMaxX(maxFrame) - frame.size.width + oobOffset, center.x - frame.size.width / 2));'''
    new='''    // SCARLET_V143_NO_EDGE_PEEK: no ~30pt edge sliver.
    CGFloat minX = CGRectGetMinX(maxFrame);
    CGFloat maxX = MAX(minX, CGRectGetMaxX(maxFrame) - frame.size.width);
    frame.origin.x = MAX(minX, MIN(maxX, center.x - frame.size.width / 2));
    if (fabs(frame.origin.x - (center.x - frame.size.width / 2)) > 1.0) {
        NSLog(@"[SCARLET_V143_WINDOW] phase=clamped_edge x=%.1f width=%.1f", frame.origin.x, frame.size.width);
    }'''
    if source.count(old)!=1:
        raise ValueError('V143 windowed frame source mismatch')
    source=source.replace(old,new,1)
    # Patch the exact minimizeWindow implementation rather than assuming
    # adjacent lifecycle/keyboard/rotation patches left the entire completion
    # block byte-for-byte identical. Preserve all pre-existing statements.
    method='- (void)minimizeWindow {'
    next_method='- (void)minimizeWindowPiP'
    if source.count(method)!=1 or source.count(next_method)!=1:
        raise ValueError('V143 minimize method boundaries mismatch')
    before,rest=source.split(method,1)
    body,after=rest.split(next_method,1)
    completion='    } completion:^(BOOL finished) {'
    hidden='        self.view.hidden = YES;'
    expected=('self.view.alpha = 0;', 'self.view.transform = CGAffineTransformIdentity;',
              '[self.view.superview sendSubviewToBack:self.view];')
    if (body.count(completion)!=1 or body.count(hidden)!=1 or
        any(body.count(token)!=1 for token in expected)):
        raise ValueError('V143 minimize lifecycle source mismatch')
    previous='        if (!finished) return;'
    if body.count(previous)>1:
        raise ValueError('V143 ambiguous old completion guard')
    if previous in body:
        body=body.replace(previous+'\n','',1)
    # Do not erase V46/V133 keyboard ownership or any later lifecycle code.
    body=body.replace(completion,completion+'''
        // SCARLET_V143_INTERRUPTED_MINIMIZE: dismiss a fading guest after
        // interrupted rotation, but do not hide an opaque reactivated scene.
        if (!finished && self.view.alpha >= 0.95) return;''',1)
    if '        self.view.alpha = 1.0;' not in body:
        body=body.replace(hidden,hidden+'\n        self.view.alpha = 1.0;',1)
    return before+method+body+next_method+after

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
