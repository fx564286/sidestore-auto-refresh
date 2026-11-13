"""P54 source-changing owner layout fix with durable one-log continuation."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
H=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
R=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
P=(ROOT/'diagnostics/SCARLET_LOG_ONLY_HANDOFF_PROMPT.md').read_text()
W=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
OWNER=G.split('// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN',1)[1].split(
    '// R6P54_OWNER_LAYOUT_CONTRACT_END',1)[0]
TRIAL=G.split('static void ScarletIslandTryP44LocalHeaderTransform(',2)[-1].split(
    'static void ScarletIslandTryDeepHeaderSafeGuideAnchor(',1)[0]

class P54NativeOwnerRepair(unittest.TestCase):
 def test_true_parent_layout_overrides_y0_only_for_unique_composite_owner(self):
  for token in (
    'ScarletIslandP54InstallNativeOwnerContract(',
    'headerKind==2 &&', 'owner.view!=parent',
    'header.nextResponder!=parent', 'beforeControls<3',
    'CGRectGetHeight(header.bounds)<34',
    'CGRectGetHeight(header.bounds)>scarletIslandP54MaximumNativeHeaderHeight',
    'method_getImplementation(guestMethod)==method_getImplementation(uiMethod)',
    'ScarletIslandDeepHeaderCountUnsafe',
    'header.frame=frame', 'frame.origin.y=guide.origin.y',
    'parent.safeAreaLayoutGuide.layoutFrame',
  ):
   self.assertIn(token, G,token)
  self.assertIn('ScarletIslandP54AfterNativeOwnerLayout(receiver);',OWNER)
  self.assertIn('((void (*)(id,SEL))originalIMP)(receiver,selector);',OWNER)
 def test_only_one_controller_instance_isa_is_changed_not_global_class(self):
  for token in (
    'objc_allocateClassPair(original,subclassName,0)',
    'objc_registerClassPair(scoped)',
    'class_addMethod(scoped,selector,body,"v@:")',
    'object_setClass(owner,scoped)',
    'object_setClass(vc,original)',
    'objc_setAssociatedObject(owner,&scarletIslandP54OwnerLayoutContractKey',
    'NSHashTable weakObjectsHashTable',
    'strstr(baseName,"NSKVONotifying_")',
    'state[@"enforcing"]=@YES',
    'state[@"enforcing"]=@NO',
  ):
   self.assertIn(token,OWNER,token)
  self.assertIn('"ScarletP54_%p",(__bridge void *)original',OWNER)
  self.assertIn('[NSValue valueWithPointer:(__bridge const void *)original]',OWNER)
  for token in ('method_setImplementation(','method_exchangeImplementations(',
                'class_replaceMethod(original','window.frame=',
                'root.frame=','header.transform=','scroll.contentInset=',
                'UIWindowScene *newScene'):
   self.assertNotIn(token,OWNER,token)
 def test_native_hit_and_window_size_are_real_rollback_conditions(self):
  for token in (
    'guest_owner_layout_contract_staged',
    'guest_owner_layout_contract_first_pass',
    'guest_owner_layout_contract_retained',
    'guest_owner_layout_contract_reverted',
    'owner_layout_passes', 'unsafe+2<=beforeControls',
    'images<=beforeImages+1','fabs(CGRectGetMinY(topRect)-safeTop)<3',
    'fabs(w.bounds.size.width-windowSize.width)<2',
    'fabs(w.bounds.size.height-windowSize.height)<2',
    'CGRectGetMinY(firstRect)>=safeTop-2',
    'CGRectGetMinY(secondRect)>=safeTop-2',
    '(int64_t)250*NSEC_PER_MSEC',
    '(int64_t)1100*NSEC_PER_MSEC',
    'head.frame=desired', 'state[@"disabled"]=@YES',
  ):
   self.assertIn(token,OWNER,token)
 def test_old_affine_not_run_on_same_composite(self):
  self.assertIn('if(headerKind==2 &&',TRIAL)
  self.assertIn('ScarletIslandP54InstallNativeOwnerContract(',TRIAL)
  self.assertIn('return;',TRIAL)
  self.assertIn('header.transform=CGAffineTransformTranslate(original,0,safeTop);',TRIAL)
  self.assertIn('"guest_owner_layout_contract_retained"',H)
  self.assertIn('onHeaderTransformVerified?(pid, true)',H)
  self.assertIn('onHeaderTransformVerified?(pid, false)',H)
 def test_next_session_log_starts_with_executable_handoff_not_just_failures(self):
  for key in ('nextEngineeringAction()', 'NEXT ENGINEERING ACTION',
      'LAST AUDITED ACTION', 'DEVICE RESULT (not inferred from CI)',
      'NEXT EXECUTABLE ACTION', 'REMEDIATION HISTORY',
      'NO-REPEAT POLICY & AI HANDOFF PROMPT'):
   self.assertIn(key,R,key)
  for key in ('실제 실행 코드를 수정', '로그를', 'L100',
      'guest_owner_layout_contract_retained', '다음 채팅',
      '진단', '위험 컨트롤 0'):
   self.assertIn(key,P,key)
  self.assertIn('scarlet-v48-r6p54-owner-layout-unsigned-20261114',W)
  self.assertIn('Scarlet-Crystal-V48-R6P54-OWNER-LAYOUT-UNSIGNED.ipa',W)
if __name__=='__main__':unittest.main()
