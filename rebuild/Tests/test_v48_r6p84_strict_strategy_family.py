"""P84 method family bans are functional tests, not a new island UI fix."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'diagnostics'))
from scarlet_distinct_strategy_gate import (  # noqa:E402
    check_distinct_method, BLOCKED_ISLAND_METHODS,
    POTENTIALLY_DISTINCT_ISLAND_METHODS)
from scarlet_no_repeat_gate import validate  # noqa:E402
HISTORY=json.loads((ROOT/'diagnostics/scarlet_remediation_history.json').read_text())
PROMPT=(ROOT/'diagnostics/SCARLET_LOG_ONLY_HANDOFF_PROMPT.md').read_text()
REC=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()


def new_island(method='guest_render_attachment_contract_repair'):
 return {
    'id':'L999','problem':'guest_top', 'incident_family':'island_content_collision',
    'mechanism':'novel_attachment_owner_contract', 'strategy_family':method,
    'operation_fingerprint':'Replace the measured incorrect render attachment owner before guest content is attached, with no offsets or masking.',
    'source_behavior_contract':'Correct native guest render attachment owner while retaining original full scene and touch responder chain.',
    'rollback_commit':'8baf32fc66d43d30ffa2881893633df5abc47a27',
    'normal_experimental_diff': {
       'normal_mode_source':'Upstream classic mode creates its guest controller under the native scene owner.',
       'resident_mode_source':'The resident mode creates a separate controller under the wrong attachment owner.',
       'proven_difference':'Comparative source and device trace proves attachment authority differs.',
       'failure_causal_link':'Misattached render owner can produce late stale top content after header layout.'},
    'alternative_strategies':[
       {'strategy_family':'guest_render_attachment_contract_repair','reason_not_selected':'Primary candidate, retained only after source evidence.'},
       {'strategy_family':'original_vs_resident_creation_path_repair','reason_not_selected':'Reject if the source creation paths already match.'},
       {'strategy_family':'native_process_scene_ownership_contract_repair','reason_not_selected':'Reject if scene process ownership already matches.'}],
    'runtime_acceptance_gate':'Signed iPhone: top overlap0, native clock/battery on, portrait landscape, touch, full scroll, Home reentry A-B-A verified.',
    'new_source_root_cause':'Actual default and resident UIKit code paths differ in render attachment ownership, unrelated to static y coordinates.',
    'code_locations':[{'file':'rebuild/HostApp/ScarletNewSceneContract.swift','location':'@@ -1,0 +1 @@',
      'before':[],'after':['let actualRenderOwnerIsCorrect = true']}]
 }


class P84StrictFamilyGate(unittest.TestCase):
 def test_immutable_old_history_does_not_fail_under_new_gate(self):
  self.assertEqual(validate(HISTORY),[])
 def test_every_previously_used_island_family_blocks_even_new_device_proof(self):
  for family,ids in BLOCKED_ISLAND_METHODS.items():
   with self.subTest(family=family):
    p=new_island(family)
    p['novelty']={'new_device_evidence':{'source_commit':'new','event':'new','observed_value':'new'}}
    errors=check_distinct_method(p,HISTORY['entries'])
    self.assertTrue(any('HARD BLOCK already-attempted island method' in e for e in errors),errors)
    self.assertTrue(ids)
 def test_reusing_same_family_with_new_file_remains_blocked(self):
  p=new_island()
  prior=dict(p,id='L140',code_locations=[{'file':'rebuild/HostApp/Old.swift'}])
  p['code_locations'][0]['file']='rebuild/HostApp/New.swift'
  errs=check_distinct_method(p,HISTORY['entries']+[prior])
  self.assertTrue(any('HARD BLOCK same operational family' in e for e in errs),errs)
 def test_unknown_renamed_family_cannot_bypass_audit(self):
  p=new_island('totally_new_magic_safe_area_fix')
  self.assertTrue(any('unregistered island strategy' in e for e in check_distinct_method(p,HISTORY['entries'])))
 def test_allowed_distinct_family_still_needs_three_alternatives_and_baseline(self):
  p=new_island();self.assertEqual(check_distinct_method(p,HISTORY['entries']),[])
  p['alternative_strategies']=[]
  self.assertTrue(any('three genuinely distinct' in e for e in check_distinct_method(p,HISTORY['entries'])))
 def test_approved_name_with_old_hidden_source_operation_still_rejected(self):
  p=new_island()
  p['code_locations'][0]['after']=['scroll.contentInset = insets',
                                 'header.frame = correctedFrame',
                                 'rootView.statusBarHidden(true)']
  errs=check_distinct_method(p,HISTORY['entries'])
  self.assertTrue(any('scroll_inset_offset' in e for e in errs),errs)
  self.assertTrue(any('header_position_or_constraint' in e for e in errs),errs)
 def test_log_export_precedes_current_run_and_has_no_exception(self):
  export=REC.split('func makeShareFile(includeHistory:',1)[1]
  self.assertIn('P84 STRICT METHOD-FAMILY BAN',export)
  self.assertLess(export.index('P84 STRICT METHOD-FAMILY BAN'),export.index('body += chunk'))
  for phrase in ('동일한 해결 방식 절대 차단','동일한 방법','normal_experimental_diff',
                 'alternative_strategies','서명', '빌드'):
   self.assertIn(phrase,PROMPT)
  self.assertIn('body += Self.decodedAudit(Self.handoffPromptBlob)',REC)
 def test_simulator_compile_first_family_requires_auditable_contract(self):
  p={
   'id':'L999','problem':'simulator_boot_masks_build','incident_family':'macos_simulator_boot_timeout_masks_iphonesimulator_compile_viability',
   'mechanism':'compile_independent_of_simulator_boot','strategy_family':'simulator_diagnostic_compile_first_runtime_stage_isolation',
   'operation_fingerprint':'Build iphonesimulator target independently before booting to preserve compilation failure evidence on an unbootable macOS hosted runner.',
   'source_behavior_contract':'Keep simulator compile and CoreSimulator runtime failures separate and preserve all real-device signing and artifact generation paths.',
   'rollback_commit':'3905b371db0d4077550baffb71e4479eca737e19'
  }
  self.assertEqual(check_distinct_method(p,HISTORY['entries']),[])
  prior=dict(p,id='L195')
  self.assertTrue(any('HARD BLOCK same operational family' in e
      for e in check_distinct_method(p,HISTORY['entries']+[prior])))
 def test_simulator_arm64_only_family_has_strict_unique_effect_contract(self):
  p={
   'id':'L999','problem':'simulator_x86_64_asm','incident_family':'simulator_x86_64_assembly_svc_in_arm_native_livecontainer_hook',
   'mechanism':'explicit_arm64_only_xcodebuild_sdk_target','strategy_family':'simulator_arm64_only_architecture_routing_for_upstream_arm_asm',
   'operation_fingerprint':'Xcode simulator diagnostic build targets only arm64 because upstream ARM svc assembly cannot compile on x86_64.',
   'source_behavior_contract':'iPhoneOS release build remains unchanged and simulator app target must exclude x86_64 assembly compilation.',
   'rollback_commit':'c0560367bfebe6d2181c337d1f4f6d4654dae08f'
  }
  self.assertEqual(check_distinct_method(p,HISTORY['entries']),[])
  self.assertTrue(any('HARD BLOCK same operational family' in e
    for e in check_distinct_method(p,HISTORY['entries']+[dict(p,id='L196')])))
 def test_new_entries_need_strict_fields_before_making_build(self):
  proposal=new_island();proposal['source_behavior_contract']='bad'
  self.assertTrue(any('source_behavior_contract' in e for e in check_distinct_method(proposal,HISTORY['entries'])))
if __name__=='__main__':unittest.main()
