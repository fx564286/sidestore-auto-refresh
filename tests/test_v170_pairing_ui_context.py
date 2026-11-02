"""V170 on-device pair UI must not hide requested operation or leak credentials."""
import unittest, importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("pairui",ROOT/"scripts/patch_v170_pairing_ui_context.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class PairingUICommandContext(unittest.TestCase):
    def test_exact_v167_pairing_handler(self):
        source='''// SCARLET_V167_ONDEVICE_UI
    private func onDevicePairCommand(_ operation: String) async {
        } catch {
            onDevicePairPhase = "failed"
            onDevicePairPin = ""
            onDevicePairDetail = V3FailureGuidance.message(error)
        }
    }
'''
        result=m.patch(source)
        self.assertEqual(m.patch(result),result)
        self.assertIn('catch let failure as CombinedFailure',result)
        self.assertIn('failure.safeMessage',result)
        self.assertIn('failure.safeCause?.rawValue',result)
        self.assertIn('typed=0 stage=command code=failed',result)
        self.assertNotIn('String(describing: error)',result)
        self.assertNotIn('NSLog("%@", error)',result)

    def test_not_applicable_to_non_pairing_ui(self):
        with self.assertRaises(ValueError):m.patch(m.OLD)

if __name__=="__main__":unittest.main()
