import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("quota", ROOT/"scripts/patch_v47_portal_budget.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class QuotaTests(unittest.TestCase):
    def test_cached_inventory_is_not_authoritative(self):
        src = "// NRG_V27_PROFILE_CAPACITY_PREFLIGHT\n" + mod.OLD
        fixed = mod.patch(src)
        self.assertIn("fetchAppIDs(for: team)", fixed)
        self.assertIn("inventory=portal_fresh", fixed)
        self.assertIn("capacity_is_estimate=1", fixed)
        self.assertIn("self.context.sharedContext?.appIDs = existing", fixed)
        self.assertNotIn("if let cached = self.context.sharedContext?.appIDs", fixed)
        self.assertNotIn("revoke", fixed)
        self.assertEqual(fixed, mod.patch(fixed))
    def test_unpinned_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "requires V27"):
            mod.patch("no V27")
        with self.assertRaisesRegex(RuntimeError, "anchor count"):
            mod.patch("// NRG_V27_PROFILE_CAPACITY_PREFLIGHT")
if __name__ == "__main__":unittest.main()
