#!/usr/bin/env python3
"""Read-only, full-tree scan of FINAL generated LiveContainer / SideStore sources.

Inventory all Swift/ObjC/ObjC++ files and fail closed on active obsolete guest
UI implementations, duplicated menus, and non-running guest shortcuts.
Do not touch historical migration scripts, profiles, credentials or containers.
"""
from pathlib import Path
import json,sys
HOST=Path('MultitaskSupport/MultitaskDockView.swift')
WINDOW=Path('MultitaskSupport/DecoratedAppSceneViewController.m')
NATIVE=Path('MultitaskSupport/AppSceneViewController.m')
SHELL=Path('LiveContainerSwiftUI/Views/V3UnifiedShell.swift')
ACTIVE_RULES={
 HOST:{
 'required':('SCARLET_V102_RECENT_FOCUS_CLOCK','SCARLET_V102_UNIFIED_ACTION_SURFACE',
   'SCARLET_V111_CANONICAL_GUEST_SWITCH_OWNER',
   'SCARLET_V112_SHARED_GUEST_UI', '@objc(SCUnifiedGuestUIBridge)',
   'nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)',
   'nrgV102PresentWindowActionsFrom:sourceView:','guard isRunning else { return nil }',
   'nrgV102NoteFocus(uuid)','nrgV102FocusDates[folder]',
   'nrgV102NoteFocus(guest.folder)'),
 'forbidden':('import ActivityKit','NRGV56IslandBar','NRGGuestActivityAttributes',
    'nrgV56RelayoutIsland','nrgV58RefreshNativeIsland',
    'UIAlertController(title: "홍수정 내부 앱 전환"',
    'lcReturnToHost', 'lcV102CollapseFloatingButton', '홍수정',
    'struct CollapsedDockView: View', 'struct CollapseButtonView: View',
    'CollapsedDockView(isHidden:', 'CollapseButtonView()',
    'keyWindow.gestureRecognizers?.removeAll',
    'struct MultitaskDockSwiftView:', 'struct AppIconView:',
    'UIHostingController<AnyView>', 'setupEdgeGestureRecognizers()',
    '48 * 60 * 60'),
 },
 WINDOW:{
 'required':('SCARLET_V102_UNIFIED_ACTION_SURFACE','nrgV102HoldWindowActions:',
    'nrgV102PresentWindowActionsFrom:self'),
 'forbidden':('- (void)nrgV72WindowOverflowLongPress:',
    'overflow.menu = [UIMenu menuWithChildren',
    'nrgV72Hold', '[SCARLET_V100_MORPH] legacy_hold_not_installed=1'),
 },
 NATIVE:{
 'required':('SCARLET_V105_LEGACY_RETURN_SOURCE_DELETED',
    'SCARLET_V104_SCENE_PROVENANCE'),
 'forbidden':('LCReturnControl','lcReturnControl','lcReturnToHost',
    'lcV76HoldToSwitch:','lcV102NativeHoldActions:',
    'viewDidLayoutSubviews {'),
 },
 SHELL:{
 'required':('V3SignInView',),
 'forbidden':('nrgV192RefreshIslandIfReady','NRGGuestActivityAttributes'),
 },
}
EXT={'.swift','.m','.mm','.h','.c','.cc','.cpp','.hpp','.metal','.py','.sh'}
def audit(host:Path,store:Path|None=None):
 problems=[]
 roots=[host]+([store] if store is not None else [])
 summary={}
 for root in roots:
  if not root.is_dir():
   problems.append(f'Missing generated root {root}')
   continue
  sources=[x for x in root.rglob('*') if x.is_file() and x.suffix in EXT and
           '.git' not in x.parts and '.build' not in x.parts and
           'DerivedData' not in x.parts]
  summary[str(root)]={'source_files_scanned':len(sources),
                      'source_bytes_scanned':sum(x.stat().st_size for x in sources),
                      'swift':sum(x.suffix=='.swift' for x in sources),
                      'objc':sum(x.suffix in {'.m','.mm','.h'} for x in sources),
                      'c_cpp':sum(x.suffix in {'.c','.cc','.cpp','.hpp'} for x in sources),
                      'other_code':sum(x.suffix in {'.metal','.py','.sh'} for x in sources)}
  if not sources:problems.append(f'No compilable source files in {root}')
  if root == host:
   # Cross-file owner audit: obsolete guest UI types or selectors must not
   # reappear in a different live runtime UI source module.
   stale=('NRGV56IslandBar','nrgV58RefreshNativeIsland',
          'nrgV192RefreshIslandIfReady','nrgV72WindowOverflowLongPress')
   for item in sources:
    rel=item.relative_to(root)
    if rel.parts[0] not in ('MultitaskSupport','LiveContainerSwiftUI'):continue
    if item.suffix not in {'.swift','.m','.mm','.h'}:continue
    data=item.read_text(encoding='utf-8',errors='replace')
    for token in stale:
     if token in data:problems.append(f'{rel}: old guest UI symbol still referenced: {token}')
 single=('SCARLET_V155_NO_DIRECT_PRESENTER' in
         (host/'LiveContainer/LCBootstrap.m').read_text(encoding='utf-8'))
 # V137 moves the ONLY guest entry to shared bootstrap for both modes.
 unified = 'SCARLET_V137_UNIFIED_GUEST_ENTRY' in (host/'LiveContainer/LCBootstrap.m').read_text(encoding='utf-8')
 # V105 no legacy button class in ANY final live-source module.
 legacy=('LCReturnControl','lcReturnControl','LCDirectReturnControl',
         'LCDirectReturnWindow','LCDirectReturnPresenter')
 for rel in (Path('MultitaskSupport/AppSceneViewController.m'),
             Path('LiveContainer/LCBootstrap.m')):
  target=host/rel
  if not target.is_file():
   problems.append(f'V105 missing compiled source {rel}')
   continue
  source=target.read_text(encoding='utf-8')
  for token in legacy:
   if token in source:problems.append(f'{rel}: obsolete control implementation {token}')
  if rel.name=='LCBootstrap.m' and not single:
   for required in ('SCARLET_V105_DIRECT_UNIFIED_MORPH',
                    'SCARLET_V112_SHARED_GUEST_UI', 'SCUnifiedGuestUIBridge',
                    'presentFrom:sourceView:', 'SCGuestMorphPresenter',
                    'scarlet.v137.shared.guest.control' if unified else 'scarlet.v105.direct.morph'):
    if required not in source:problems.append(f'{rel}: unified Direct morph missing {required}')
   for obsolete in ('UIButton *scrim','UIView *card','UILabel *note',
                    '- (void)expand:', 'systemImageNamed:@"chevron.up"'):
    if obsolete in source:problems.append(f'{rel}: separate Direct panel remains {obsolete}')
 if single:
  boot=(host/'LiveContainer/LCBootstrap.m').read_text(encoding='utf-8')
  if 'SCARLET_V155_NO_DIRECT_PRESENTER' not in boot:
   problems.append('V155 bootstrap owner marker missing')
  for old in ('SCGuestMorphPresenter','SCGuestMorphWindow',
              'scarletcrystal251://nrg-guest-controls'):
   if old in boot:problems.append(f'V155 Direct code survived: {old}')
  doc=(host/HOST).read_text(encoding='utf-8')
  if 'SCARLET_V155_DOCK_SINGLE_MODE' not in doc:
   problems.append('V155 native LiveProcess picker missing')
  if '@objc(SCUnifiedGuestUIBridge)' in doc:
   problems.append('V155 removed Direct bridge survived')
 if unified:
  ACTIVE_RULES[WINDOW]['required'] = ('SCARLET_V137_UNIFIED_GUEST_ENTRY', 'SCARLET_V137_TOUCH_SETTLE')
 for rel,rules in ACTIVE_RULES.items():
  target=host/rel
  if not target.is_file():
   problems.append(f'Missing active guest target {rel}')
   continue
  s=target.read_text(encoding='utf-8')
  required=rules['required']
  if single and rel==HOST:
   required=tuple(x for x in required if x not in
     ('SCARLET_V112_SHARED_GUEST_UI','@objc(SCUnifiedGuestUIBridge)'))
  for token in required:
   if token not in s: problems.append(f'{rel}: required active source missing {token}')
  for token in rules['forbidden']:
   if token in s: problems.append(f'{rel}: obsolete implementation retained {token}')
 # V105 deliberately deleted the V103 native control. Preserve the
 # still-active virtual guest switcher and reject a missing final owner.
 if 'SCARLET_V105_LEGACY_RETURN_SOURCE_DELETED' in (host/NATIVE).read_text(encoding='utf-8'):
  virtual=(host/WINDOW).read_text(encoding='utf-8')
  dock=(host/HOST).read_text(encoding='utf-8')
  for marker in (('SCARLET_V137_UNIFIED_GUEST_ENTRY','SCARLET_V137_TOUCH_SETTLE') if unified
                 else ('SCARLET_V103_VIRTUAL_ONLY_CONTROL','scarlet.v103.virtual.guest.control')):
   if marker not in virtual:problems.append(f'V105 preserved virtual owner missing {marker}')
  for marker in ('SCARLET_V103_IMMEDIATE_GUEST_SWITCH','defer { dismissSelection() }'):
   if marker not in dock:problems.append(f'V105 preserved native guest switch missing {marker}')
 # V103: ensure ownership is mode-exclusive in the FINAL compiled files,
 # rather than accepting dead V41 early returns or delayed switch callbacks.
 native_text=(host/NATIVE).read_text(encoding='utf-8') if (host/NATIVE).is_file() else ''
 virtual_text=(host/WINDOW).read_text(encoding='utf-8') if (host/WINDOW).is_file() else ''
 dock_text=(host/HOST).read_text(encoding='utf-8') if (host/HOST).is_file() else ''
 if 'SCARLET_V103_SINGLE_CONTROL_OWNER' in native_text:
  required={
   NATIVE:('if (virtualWindowGuest)', 'scarlet.v103.native.guest.control',
           'restored_and_dispatched=1'),
   WINDOW:(('SCARLET_V137_UNIFIED_GUEST_ENTRY','SCARLET_V137_TOUCH_SETTLE') if unified
           else ('SCARLET_V103_VIRTUAL_ONLY_CONTROL','scarlet.v103.virtual.guest.control')),
   HOST:('SCARLET_V103_IMMEDIATE_GUEST_SWITCH','defer { dismissSelection() }')
  }
  for rel,tokens in required.items():
   source=(host/rel).read_text(encoding='utf-8') if (host/rel).is_file() else ''
   for t in tokens:
    if t not in source:problems.append(f'{rel}: missing V103 mode-exclusive owner/switch {t}')
  if 'return;\n    if (!self.lcReturnControl)' in native_text:
   problems.append('V41 unconditional early return survived V103 Direct native guest path')
  if 'item.addAction(UIAction { [weak self] _ in\n                collapse {' in dock_text:
   problems.append('Guest switch still waits for close animation')
 elif 'SCARLET_V105_LEGACY_RETURN_SOURCE_DELETED' not in native_text and (
       'SCARLET_V103_IMMEDIATE_GUEST_SWITCH' in dock_text or
       'SCARLET_V103_VIRTUAL_ONLY_CONTROL' in virtual_text):
  problems.append('Partial V103 ownership migration; native controller missing')
 # V104: fail a partially deployed scene reactivation patch while leaving
 # all guest/user data untouched. Presence checks only; no private-path reads.
 v104_in_dock='SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND' in dock_text
 v104_in_app='SCARLET_V104_SCENE_PROVENANCE' in native_text
 if v104_in_dock != v104_in_app:
  problems.append('V104 remote scene reactivation diagnostic was only half applied')
 if v104_in_dock:
  for token in ('bringViewToFront(view, in: window)',
                'controller?.appSceneVC.view.layoutIfNeeded()',
                '[SCARLET_V104_GUEST]'):
   if token not in dock_text:problems.append(f'V104 missing retained scene {token}')
  if dock_text.index('bringViewToFront(view, in: window)',dock_text.index('SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND')) > dock_text.index('controller?.lcResumeMinimizedGuest()',dock_text.index('SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND')):
   problems.append('V104 returned to premature foreground activation')
 if v104_in_app:
  for token in ('[SCARLET_V104_CONTAINER]',
                '[SCARLET_V104_SCENE]',
                'if (!running || !presenterAvailable) return;'):
   if token not in native_text:problems.append(f'V104 missing scene provenance {token}')
 return {'status':'PASS' if not problems else 'FAIL',
         'scope':'all generated source languages, cross-file retired UI symbols, and four live UI owners',
         'trees':summary,'errors':problems}
if __name__=='__main__':
 if len(sys.argv) not in (2,3):raise SystemExit('usage: audit_v102_final_source.py host [embedded-sideStore]')
 x=audit(Path(sys.argv[1]),Path(sys.argv[2]) if len(sys.argv)==3 else None)
 print(json.dumps(x,ensure_ascii=False,indent=2))
 raise SystemExit(0 if x['status']=='PASS' else 2)
