#!/usr/bin/env python3
"""V169: UIKit event-driven guest viewport, authenticated transient RP discovery.

Apply after V151/V141 geometry and V164 RemotePairing. No persisted pair,
Apple identity, app container, bundle identifier, or VPN preference is touched.
"""
from pathlib import Path
import sys

def one(s, before, after, label):
    n = s.count(before)
    if n != 1:
        raise ValueError(f"V169 {label} anchor count={n}")
    return s.replace(before, after, 1)

def decorated(s):
    marker = 'SCARLET_V169_EVENT_DRIVEN_VIEWPORT'
    if marker in s:
        if s.count('// ' + marker + ':') != 1 or 'nrgV169ScheduleGeometry' not in s:
            raise ValueError('V169 decorated partial')
        return s
    for prerequisite in ('SCARLET_V136_ROTATION_ATOMIC',
                         'SCARLET_V141_INSET_AWARE_SETTLE',
                         'SCARLET_V151_UNIFIED_GUEST_GEOMETRY'):
        if prerequisite not in s:
            raise ValueError('V169 missing ' + prerequisite)
    # A SwiftUI safe-area child can retain landscape insets while its owning
    # UIWindow has already transitioned to portrait. Only the window owns
    # the physical exclusion. Guest scene metadata remains separate.
    s = one(s,
        'portraitTop = MAX(physicalInsets.top, self.view.superview.safeAreaInsets.top);',
        'portraitTop = physicalInsets.top;', 'physical top inset')
    s = one(s,
        'portraitBottom = MAX(physicalInsets.bottom, self.view.superview.safeAreaInsets.bottom);',
        'portraitBottom = physicalInsets.bottom;', 'physical bottom inset')
    anchor = '@property(nonatomic) UIInterfaceOrientation nrgV55LastHostOrientation;'
    s = one(s, anchor, anchor + '''
// SCARLET_V169_EVENT_DRIVEN_VIEWPORT: observe committed window geometry.
@property(nonatomic) CGRect nrgV169LastMeasuredViewport;
@property(nonatomic) UIEdgeInsets nrgV169LastMeasuredInsets;
@property(nonatomic) CGSize nrgV169LastMeasuredSize;
@property(nonatomic) UIInterfaceOrientation nrgV169LastMeasuredOrientation;
@property(nonatomic) BOOL nrgV169GeometryQueued;''', 'layout state')
    hook = '''// The embedded scene must follow actual UIKit layout/safe-area changes,
// including full-screen video exit. Do not guess animation completion times.
- (void)nrgV169ScheduleGeometry {
    if (!self.isMaximized || !self.appSceneVC.isAppRunning || self.view.hidden) return;
    UIWindow *window = self.view.window;
    if (!window || !self.view.superview || ![self nrgV136GeometryStable:window]) return;
    CGRect measured = [self.view.superview convertRect:self.view.frame toView:window];
    CGSize size = window.bounds.size;
    UIEdgeInsets insets = window.safeAreaInsets;
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    if (CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport) &&
        CGSizeEqualToSize(size, self.nrgV169LastMeasuredSize) &&
        UIEdgeInsetsEqualToEdgeInsets(insets, self.nrgV169LastMeasuredInsets) &&
        orientation == self.nrgV169LastMeasuredOrientation) return;
    self.nrgV169LastMeasuredViewport = measured;
    self.nrgV169LastMeasuredSize = size;
    self.nrgV169LastMeasuredInsets = insets;
    self.nrgV169LastMeasuredOrientation = orientation;
    if (self.nrgV169GeometryQueued) return;
    self.nrgV169GeometryQueued = YES;
    __weak typeof(self) weakSelf = self;
    dispatch_async(dispatch_get_main_queue(), ^{
        __strong typeof(weakSelf) owner = weakSelf;
        if (!owner) return;
        owner.nrgV169GeometryQueued = NO;
        [owner nrgV55ReconcileRotationGeometry];
        NSLog(@"[SCARLET_V169_VIEWPORT] stage=layout_event host=%ld size=%.0fx%.0f top=%.1f viewY=%.1f",
              (long)orientation, size.width, size.height, insets.top, measured.origin.y);
    });
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    [self nrgV169ScheduleGeometry];
}

- (void)viewSafeAreaInsetsDidChange {
    [super viewSafeAreaInsetsDidChange];
    [self nrgV169ScheduleGeometry];
}

'''
    return one(s, '- (void)nrgV55ReconcileRotationGeometry {',
               hook + '- (void)nrgV55ReconcileRotationGeometry {',
               'UIKit callbacks')

def delegate(s):
    mark = 'SCARLET_V169_DEFERRED_ROTATION_RETIRED'
    if mark in s:
        if s.count(mark) != 1: raise ValueError('V169 delegate partial')
        return s
    if 'SCARLET_V141_ROTATION_SAFEAREA_SETTLE' not in s:
        raise ValueError('V169 delegate needs V141')
    old = '''            DispatchQueue.main.asyncAfter(deadline: .now() + 0.10) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
            // SCARLET_V141_ROTATION_SAFEAREA_SETTLE: iOS 27 often settles
            // top safe-area AFTER UIWindow width/height have stabilized.
            // Two final bounded checks, never a repeating timer.
            for delay in [0.55, 0.95] {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak windowScene] in
                    guard let windowScene, windowScene.activationState == .foregroundActive else { return }
                    MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
                }
            }'''
    new = '''            // SCARLET_V169_DEFERRED_ROTATION_RETIRED: delegate posts one
            // reconciliation; further updates arrive from UIKit layout and
            // safe-area callbacks, not four arbitrary elapsed-time probes.'''
    return one(s, old, new, 'fixed rotation timers')

def pairing(s):
    marker = 'SCARLET_V169_NO_VPN_PEER_FALLBACK'
    if marker in s:
        if s.count(marker + ':') != 1: raise ValueError('V169 pairing partial')
        return s
    if 'SCARLET_V164_TRANSPORT_RESYNC' not in s:
        raise ValueError('V169 pairing needs V164')
    old = '''        guard let initialHost = gateway.deviceEndpointIp, !initialHost.isEmpty else {
            throw firstError
        }
        let initialPort = gateway.getPort(for: .rppairing)'''
    new = '''        // SCARLET_V169_NO_VPN_PEER_FALLBACK: utun may exist with no peer.
        // A vetted _remotepairing._tcp discovery can provide an ephemeral
        // candidate; the full paired handshake, never TCP reachability,
        // determines whether the candidate is usable.
        guard let initialHost = gateway.deviceEndpointIp, !initialHost.isEmpty else {
            let now = Date()
            guard now.timeIntervalSince(lastV140BonjourRetryTime) >= 5 else {
                NSLog("[SCARLET_V169_RP] stage=transport reason=missing_vpn_peer retry=throttled")
                throw firstError
            }
            lastV140BonjourRetryTime = now
            guard let discovered = await resolveV140RemotePairingEndpoint() else {
                NSLog("[SCARLET_V169_RP] stage=transport reason=missing_vpn_peer discovery=absent")
                throw firstError
            }
            guard gateway.deviceEndpointIp == nil || gateway.deviceEndpointIp == "" else {
                NSLog("[SCARLET_V169_RP] stage=transport reason=route_changed discovery=ignored")
                throw firstError
            }
            let previousPort = gateway.getPort(for: .rppairing)
            gateway.setDeviceEndpointIp(discovered.host)
            gateway.setPort(discovered.port, for: .rppairing)
            do {
                let verified = try await operation()
                NSLog("[SCARLET_V169_RP] stage=authenticated_probe result=success")
                return verified
            } catch {
                if gateway.deviceEndpointIp == discovered.host &&
                   gateway.getPort(for: .rppairing) == discovered.port {
                    gateway.setDeviceEndpointIp(nil)
                    gateway.setPort(previousPort, for: .rppairing)
                }
                NSLog("[SCARLET_V169_RP] stage=authenticated_probe result=failed record=preserved")
                throw error
            }
        }
        let initialPort = gateway.getPort(for: .rppairing)'''
    return one(s, old, new, 'no usable utun peer')

def apply(root, mode):
    if mode == 'layout':
        transforms = [
            (root / 'MultitaskSupport/DecoratedAppSceneViewController.m', decorated),
            (root / 'LiveContainerSwiftUI/App/AppDelegate.swift', delegate),
        ]
    elif mode == 'pairing':
        transforms = [(root / 'SideStore/Core/DeviceApi/MinimuxerWrapper.swift', pairing)]
    else:
        raise ValueError('mode must be layout or pairing')
    pending = []
    for path, transform in transforms:
        if not path.is_file() or path.is_symlink():
            raise ValueError('V169 missing host file ' + str(path))
        before = path.read_text(encoding='utf-8')
        after = transform(before)
        if transform(after) != after:
            raise ValueError('V169 patch not idempotent: ' + str(path))
        pending.append((path, before, after))
    for path, before, after in pending:
        if before != after:
            path.write_text(after, encoding='utf-8')
    print('[PASS] V169 event geometry/transport', mode)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: patch_v169_event_geometry_transport.py <root> <layout|pairing>')
    apply(Path(sys.argv[1]), sys.argv[2])
