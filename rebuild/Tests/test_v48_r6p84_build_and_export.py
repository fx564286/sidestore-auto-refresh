"""P84 release must run Xcode after strict method audit and embed actual prompt."""
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]
WF=(P.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
INTEGRATION=(P/'integration/apply_scarlet_host.py').read_text()
REC=(P/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
GATE=(P/'diagnostics/scarlet_no_repeat_gate.py').read_text()
class P84BuildAndExport(unittest.TestCase):
 def test_new_release_branch_eligible_at_every_level(self):
  branch='fix/scarlet-v48-r6p84-strict-distinct-methods-20261116'
  self.assertIn(branch,WF.splitlines()[5])
  pub=next(x for x in WF.splitlines() if x.strip().startswith("if: github.event_name == 'push'") and 'refs/heads' in x)
  self.assertIn("github.ref == 'refs/heads/"+branch+"'",pub)
  for x in ('--host-build-version 3.8.84','version="3.8.84"',
           '"r6p84"','scarlet-v48-r6p84-strategy-gate-unsigned-20261116',
           'Scarlet-Crystal-V48-R6P84-STRATEGY-GATE-UNSIGNED.ipa'):
   self.assertIn(x,WF)
 def test_real_binary_embeds_handoff_prompt_not_just_markdown_in_repo(self):
  self.assertIn('handoff_path.read_bytes()',INTEGRATION)
  self.assertIn('recorder.write_text(r, encoding="utf-8")',INTEGRATION)
  self.assertIn('P84 STRICT METHOD-FAMILY BAN',REC)
  self.assertIn('body += Self.decodedAudit(Self.handoffPromptBlob)',REC)
  self.assertIn('body += Self.decodedAudit(Self.remediationHistoryBlob)',REC)
 def test_ci_uses_no_repeat_repo_gate_before_xcode(self):
  self.assertIn('python3 rebuild/diagnostics/scarlet_no_repeat_gate.py --repository-check',WF)
  self.assertIn('python3 -m unittest discover -s rebuild/Tests -p',WF)
  self.assertIn('if _entry_number(entry) >= 140:',GATE)
  self.assertIn('check_distinct_method(proposal, entries)',GATE)
if __name__=='__main__':unittest.main()
