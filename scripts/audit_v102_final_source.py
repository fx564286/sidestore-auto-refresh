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
EXT={'.swift','.m','.mm','.h'}
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
                      'objc':sum(x.suffix in {'.m','.mm','.h'} for x in sources)}
  if not sources:problems.append(f'No compilable source files in {root}')
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
 return {'status':'PASS' if not problems else 'FAIL',
         'scope':'whole generated Swift/ObjC source trees; guest UI enforcement in 4 live owner files',
         'trees':summary,'errors':problems}
if __name__=='__main__':
 if len(sys.argv) not in (2,3):raise SystemExit('usage: audit_v102_final_source.py host [embedded-sideStore]')
 x=audit(Path(sys.argv[1]),Path(sys.argv[2]) if len(sys.argv)==3 else None)
 print(json.dumps(x,ensure_ascii=False,indent=2))
 raise SystemExit(0 if x['status']=='PASS' else 2)
