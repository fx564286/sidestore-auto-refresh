"""P83 native build success must qualify its matching unsigned GitHub Release."""
from pathlib import Path
import re,unittest
P=Path(__file__).resolve().parents[1]
WF=(P.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class P83ReleaseEligibility(unittest.TestCase):
 def test_publish_job_not_skipped_for_p83_branch(self):
  line=next(x for x in WF.splitlines() if x.strip().startswith("if: github.event_name == 'push'") and 'refs/heads' in x)
  self.assertIn("github.ref == 'refs/heads/fix/scarlet-v48-r6p83-single-statusbar-authority-20261116'",line)
  self.assertEqual(line.count("fix/scarlet-v48-r6p83-single-statusbar-authority-20261116"),1)
 def test_p83_ipa_release_uses_same_branch(self):
  key='if [ "$GITHUB_REF" = "refs/heads/fix/scarlet-v48-r6p83-single-statusbar-authority-20261116" ]; then'
  self.assertIn(key,WF)
  self.assertIn('tag=scarlet-v48-r6p83-statusbar-owner-unsigned-20261116',WF)
  self.assertIn('asset=Scarlet-Crystal-V48-R6P83-STATUSBAR-OWNER-UNSIGNED.ipa',WF)
  self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.83)',WF)
if __name__=='__main__':unittest.main()
