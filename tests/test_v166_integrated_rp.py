import importlib.util
from pathlib import Path
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v166',ROOT/'scripts/patch_v166_integrated_rp.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class RPInboxTests(unittest.TestCase):
    def test_unknown_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'V166 requires V165'):
            mod.patch('unknown')
    def test_only_one_inbox_candidate_autoimports_through_old_service(self):
        p=Path(os.environ.get('V166_GENERATED_SHELL',''))
        if not p.is_file(): return
        s=p.read_text()
        self.assertEqual(mod.patch(s),s)
        self.assertIn('V3PairingPresentationPolicy.state(statusConnected: status.connected,',s)
        self.assertIn('automaticImportAttempted = true',s)
        self.assertIn('Task { await importFile(file) }',s)
        self.assertIn('V3ServiceBridge.shared.request(operation: "pairingImportData", target: token)',s)
        self.assertIn('eligible.count == 1 ? eligible[0] : nil',s)
        self.assertIn('FileManager.default.fileExists(atPath:',s)
        self.assertIn('Inbox/Scarlet-RemotePairing.plist',s)
        self.assertEqual(s.count('[SCARLET_V166_AUTOMATIC_RP_HANDOFF]'),1)
        self.assertEqual(s.count('struct V3PairingView: View {'),1)
        self.assertEqual(s.count('struct V3SetupAssistantView: View {'),1)
if __name__=='__main__':unittest.main()
