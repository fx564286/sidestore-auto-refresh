"""V47: unsigned Apple memory capability requests are never reported as grants."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=(ROOT/"scripts/nrg_v47_widgetless_install_oneclick.sh").read_text()
class MemoryGrantTests(unittest.TestCase):
    def test_actual_profile_entitlement_is_authority(self):
        self.assertIn("memory_key='com.apple.developer.kernel.increased-memory-limit'",SCRIPT)
        self.assertIn("get('Entitlements',{}).get(memory_key) is True",SCRIPT)
        self.assertIn("increased_memory_granted=",SCRIPT)
        self.assertIn("No profile grants Increased Memory Limit",SCRIPT)
        self.assertIn("device jetsam limits remain",SCRIPT)
        self.assertNotIn("unlimited_memory_granted=true",SCRIPT)
    def test_preflight_remains_non_destructive(self):
        self.assertIn("ideviceinstaller -u \"$U\" upgrade \"$S\"",SCRIPT)
        self.assertIn('BRANCH=fix/nrg-v47-four-issue-recovery-20261018', SCRIPT)
        self.assertNotIn("ideviceinstaller -u \"$U\" uninstall",SCRIPT)
        self.assertIn("if missing: sys.exit",SCRIPT)

if __name__=='__main__': unittest.main()
