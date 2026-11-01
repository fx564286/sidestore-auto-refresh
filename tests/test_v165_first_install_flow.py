"""V165 installer-level UI regression (without imported licensed SideInstaller source)."""
from pathlib import Path
import importlib.util
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v165',ROOT/'scripts/patch_v165_first_install_flow.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class V165FirstRun(unittest.TestCase):
    def test_source_guard_rejects_unknown(self):
        with self.assertRaisesRegex(ValueError,'missing V164 shell prerequisite'):
            mod.patch('unknown')
    def test_one_primary_next_action(self):
        root=os.getenv('V165_PATCHED_LIVECONTAINER')
        if not root:return
        s=(Path(root)/mod.SWIFT).read_text()
        self.assertEqual(mod.patch(s),s)
        for anchor in ('SCARLET_V165_FIRST_INSTALL','SCARLET_V165_INBOX_REUSE',
                       'SCARLET_V165_FIRST_LAUNCH',
                       'SCARLET_V165_SINGLE_NEXT_ACTION',
                       'SCARLET_V165_LEGACY_HELP_COLLAPSED',
                       'case "pairing":','case "account":', 'case "tunnel":',
                       'case "jitless":','case "verify":','case "review":',
                       'setup.isComplete(status: status) ? "complete" : "review"',
                       'setup.runTestRefresh(status: status)',
                       'V3SignInView().environmentObject(status)',
                       'openCanonicalJITLessSetup()',
                       'openLocalVPN()',
                       '[SCARLET_V165_FIRST_INSTALL] action=reload_confirmed'):
            self.assertIn(anchor,s)
        self.assertIn('UserDefaults.standard.set(true, forKey: "ScarletV165InitialSetupOpened")',s)
        self.assertIn('V3SetupReloadRecomputePolicy.mayRecompute(',s)
        self.assertEqual(s.count('struct V3SetupAssistantView: View {'),1)
        self.assertEqual(s.count('struct V3PairingView: View {'),1)
        self.assertEqual(s.count('accessibilityIdentifier("scarletV165ContinuePairing")'),1)
    def test_pairing_files_are_only_one_tap_candidate_never_auto_saved(self):
        root=os.getenv('V165_PATCHED_LIVECONTAINER')
        if not root:return
        s=(Path(root)/mod.SWIFT).read_text()
        pair=s[s.index('struct V3PairingView: View {'):s.index('@MainActor\nfinal class V3SettingsStore',s.index('struct V3PairingView: View {'))]
        self.assertIn('eligible.count == 1 ? eligible[0] : nil',pair)
        self.assertIn('file.pathExtension.lowercased()',pair)
        self.assertIn('let inbox = documents.appendingPathComponent("Inbox", isDirectory: true)',pair)
        self.assertIn('Button("Choose a Pairing File")',pair)
        self.assertIn('Task { await importFile(receivedPairingFile) }',pair)
        self.assertIn('V3SharedFileInput.readBoundedAsync(url)',pair)
        self.assertIn('V3ServiceBridge.shared.request(operation: "pairingImportData", target: token)',pair)
        self.assertIn('DisclosureGroup("Advanced: computer-assisted pairing")',pair)
        self.assertNotIn('private_key',pair)
        self.assertNotIn('SecItemDelete',pair)
    def test_no_change_to_lc_floating_controls(self):
        root=os.getenv('V165_PATCHED_LIVECONTAINER')
        if not root:return
        s=(Path(root)/mod.SWIFT).read_text()
        for control in ('V3_UNIFIED_SHELL_V1_BEGIN','V3_PAIRING_PLACEMENT_FIRST_V1',
                        'V3_REFRESH_PREREQUISITE_POLICY_V1'):
            self.assertIn(control,s)
        self.assertNotIn('SCGuestMorphPresenter',s)
if __name__=='__main__':unittest.main()
