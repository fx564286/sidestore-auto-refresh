#!/usr/bin/env python3
"""Window-only overflow controls without restoring the title bar."""
from pathlib import Path
import sys
P='MultitaskSupport/DecoratedAppSceneViewController.m'
M='NRG_V37_WINDOW_ONLY_OVERFLOW'
def patch(s):
    if M in s:return s
    a='@property(nonatomic) UIBarButtonItem *maximizeButton;'
    b=a+'\n@property(nonatomic, strong) UIButton *nrgWindowOverflow; // '+M
    assert s.count(a)==1;s=s.replace(a,b,1)
    a='    [self.view addSubview:self.resizeHandle];'
    b=a+'''

    // NRG: overlay is independent of the navigation bar and adds no layout row.
    UIButton *overflow = [UIButton buttonWithType:UIButtonTypeSystem];
    self.nrgWindowOverflow = overflow;
    overflow.translatesAutoresizingMaskIntoConstraints = NO;
    [overflow setImage:[UIImage systemImageNamed:@"ellipsis"] forState:UIControlStateNormal];
    overflow.tintColor = UIColor.labelColor;
    overflow.backgroundColor = [UIColor.secondarySystemBackgroundColor colorWithAlphaComponent:0.88];
    overflow.layer.cornerRadius = 17;
    overflow.accessibilityLabel = @"Window controls";
    __weak typeof(self) weakOverflowSelf = self;
    overflow.menu = [UIMenu menuWithChildren:@[
        [UIAction actionWithTitle:@"Minimize" image:[UIImage systemImageNamed:@"minus"] identifier:nil handler:^(__kindof UIAction *action) { [weakOverflowSelf minimizeWindow]; }],
        [UIAction actionWithTitle:@"Maximize / Restore" image:[UIImage systemImageNamed:@"arrow.up.left.and.arrow.down.right"] identifier:nil handler:^(__kindof UIAction *action) { [weakOverflowSelf maximizeWindow]; }],
        [UIAction actionWithTitle:@"Close" image:[UIImage systemImageNamed:@"xmark"] identifier:nil handler:^(__kindof UIAction *action) { [weakOverflowSelf closeWindow]; }]
    ]];
    overflow.showsMenuAsPrimaryAction = YES;
    [self.view addSubview:overflow];
    [NSLayoutConstraint activateConstraints:@[
        [overflow.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-8],
        [overflow.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:6],
        [overflow.widthAnchor constraintEqualToConstant:34],
        [overflow.heightAnchor constraintEqualToConstant:34]
    ]];'''
    assert s.count(a)==1;s=s.replace(a,b,1)
    return s
if __name__=='__main__':
 p=Path(sys.argv[1])/P;s=p.read_text();t=patch(s)
 if t!=s:p.write_text(t)
 print('[PASS] V37 independent window-only overflow')
