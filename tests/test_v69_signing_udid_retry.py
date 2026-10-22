"""Install self-resign must not collapse transient RemotePairing failure into fake identity."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v69', ROOT/'scripts/patch_v69_signing_udid_retry.py')
v69 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v69)

class ResignUDIDRetryTest(unittest.TestCase):
    def test_pinned_block_replacement_is_idempotent(self):
        sample='PREPARE\n' + v69.OLD + '        importantOriginalLogic()\n'
        updated=v69.patch(sample)
        self.assertIn('importantOriginalLogic()',updated)
        self.assertEqual(1,updated.count(v69.MARKER))
        self.assertEqual(updated,v69.patch(updated))

    def test_never_fakes_or_reuses_a_device_identifier(self):
        source=v69.NEW
        self.assertIn('observedUDID = try await fetchUDID()',source)
        self.assertIn('throw OperationError.unknownUDID',source)
        self.assertIn('try Task.checkCancellation()',source)
        self.assertIn('throw CancellationError()',source)
        self.assertIn('if attempt == 4 { throw error }',source)
        self.assertNotIn('UserDefaults.standard.string(forKey:',source)
        self.assertNotIn('Bundle.main.object(forInfoDictionaryKey: Bundle.Info.deviceID)',source)
        self.assertEqual(1,source.count('for attempt in 1...4'))
        self.assertIn('turnOnDataIfNeeded()',source)

    def test_wrong_pinned_revision_refuses_to_patch(self):
        with self.assertRaisesRegex(ValueError,'pinned resign'):
            v69.patch('if targetAppBundle.isAltStoreApp { /* changed in upstream */ }')
        with self.assertRaisesRegex(ValueError,'Partial V69'):
            v69.patch(v69.NEW+v69.OLD)

    def test_ci_applies_patch_to_real_side_store_source(self):
        workflow=(ROOT/'.github/workflows/livecontainer-build.yml').read_text()
        self.assertIn('patch_v69_signing_udid_retry.py work/EmbeddedSideStore',workflow)
        self.assertIn('swiftc -frontend -parse work/EmbeddedSideStore/SideStore/Core/Operations/PipelineOperations/ResignAppOperation.swift',workflow)

if __name__ == '__main__':
    unittest.main()
