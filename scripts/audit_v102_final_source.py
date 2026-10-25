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
   'nrgV102PresentWindowActionsFrom:sourceView:','guard isRunning else { return nil }',
   'nrgV102NoteFocus(uuid)','nrgV102FocusDates[folder]','dockView?.isHidden = true',
   'dockView?.isHidden = previousDockHidden'),
 'forbidden':('import ActivityKit','NRGV56IslandBar','NRGGuestActivityAttributes',
    'nrgV56RelayoutIsland','nrgV58RefreshNativeIsland',
    'UIAlertController(title: "홍수정 내부 앱 전환"',
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
 'required':('SCARLET_V102_NATIVE_GESTURE_CLEANUP','lcV102NativeHoldActions:',
    'lcV102CollapseFloatingButton','nrgV102PresentWindowActionsFrom:self'),
 'forbidden':('lcV76HoldToSwitch:','v76Hold.enabled = NO',
    'self.lcReturnControl.button.menu = [UIMenu',
    '(^switchAction)(void)'),
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
 for rel,rules in ACTIVE_RULES.items():
  target=host/rel
  if not target.is_file():
   problems.append(f'Missing active guest target {rel}')
   continue
  s=target.read_text(encoding='utf-8')
  for token in rules['required']:
   if token not in s: problems.append(f'{rel}: required active source missing {token}')
  for token in rules['forbidden']:
   if token in s: problems.append(f'{rel}: obsolete implementation retained {token}')
 # V103: ensure ownership is mode-exclusive in the FINAL compiled files,
 # rather than accepting dead V41 early returns or delayed switch callbacks.
 native_text=(host/NATIVE).read_text(encoding='utf-8') if (host/NATIVE).is_file() else ''
 virtual_text=(host/WINDOW).read_text(encoding='utf-8') if (host/WINDOW).is_file() else ''
 dock_text=(host/HOST).read_text(encoding='utf-8') if (host/HOST).is_file() else ''
 if 'SCARLET_V103_SINGLE_CONTROL_OWNER' in native_text:
  required={
   NATIVE:('if (virtualWindowGuest)', 'scarlet.v103.native.guest.control',
           'restored_and_dispatched=1'),
   WINDOW:('SCARLET_V103_VIRTUAL_ONLY_CONTROL',
           'scarlet.v103.virtual.guest.control'),
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
 elif ('SCARLET_V103_IMMEDIATE_GUEST_SWITCH' in dock_text or
       'SCARLET_V103_VIRTUAL_ONLY_CONTROL' in virtual_text):
  problems.append('Partial V103 ownership migration; native controller missing')
 return {'status':'PASS' if not problems else 'FAIL',
         'scope':'all generated source languages, cross-file retired UI symbols, and four live UI owners',
         'trees':summary,'errors':problems}
if __name__=='__main__':
 if len(sys.argv) not in (2,3):raise SystemExit('usage: audit_v102_final_source.py host [embedded-sideStore]')
 x=audit(Path(sys.argv[1]),Path(sys.argv[2]) if len(sys.argv)==3 else None)
 print(json.dumps(x,ensure_ascii=False,indent=2))
 raise SystemExit(0 if x['status']=='PASS' else 2)
