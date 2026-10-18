#!/usr/bin/env python3
"""Contract checks for the optional external SideJITServer settings patch."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nrg_v45", ROOT / "scripts/patch_v45_builtin_settings.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SettingsFirstTests(unittest.TestCase):
    def test_boot_default_off_skips_server_discovery(self):
        patched = module.patch_boot(module.BOOT_OLD)
        self.assertIn("SideJITServer disabled; external discovery skipped", patched)
        self.assertNotIn("isSideJITServerDetected()", patched)
        self.assertNotIn("SideJITServer Enabled", patched)
        self.assertIn("isSideJITServerEnabled", patched)
        self.assertEqual(module.patch_boot(patched), patched)

    def test_ui_reports_unavailable_without_affecting_vpn(self):
        mock = (
            'Text("Required for JIT on iOS 17+")\n'
            'footer: Text("Leave empty to automatically discover SideJITServer on your local network via Bonjour.")\n'
            'Text(resolvedAddress.isEmpty ? "Resolving…" : resolvedAddress)\n'
            + module.UI_OLD + "\n"
            + '''                } else {
                    connectionStatus = .disabled
                }
            }
        }
    }
''' + '''        guard isServerEnabled else {
            connectionStatus = .disabled
            debugLog("[SideJITConfig] refreshServerState: SideJITServer is disabled")
'''
        )
        patched = module.patch_view(mock)
        self.assertIn('Not discovered', patched)
        self.assertIn('guard !serverURL.isEmpty else', patched)
        self.assertIn('Local VPN', patched)
        self.assertIn('resolvedAddress = ""', patched)
        self.assertEqual(module.patch_view(patched), patched)

    def test_pinned_sources_if_available(self):
        base = os.environ.get("EMBEDDED_SIDESTORE_TEST_SOURCE") or os.environ.get("SIDESTORE_TEST_SOURCE")
        if not base:
            self.skipTest("Pinned SideStore checkout unavailable outside CI")
        root = Path(base)
        for rel, fn in ((module.BOOT, module.patch_boot), (module.VIEW, module.patch_view)):
            source = (root / rel).read_text()
            updated = fn(source)
            self.assertEqual(fn(updated), updated)
            self.assertIn(module.MARK, updated)

if __name__ == "__main__":
    unittest.main()
