"""Preserve the 4-column installed-apps presentation while rebalancing vertical rhythm."""
from pathlib import Path
import unittest

UI = (Path(__file__).resolve().parents[1] / "Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class InstalledAppsGridBalanceTests(unittest.TestCase):
    def test_four_columns_and_existing_app_tile_size(self):
        self.assertIn("count: 4)", UI)
        self.assertIn(".frame(width: 66, height: 66)", UI)
        self.assertIn('"SCARLET_APPS_FOUR_COLUMN_LAUNCHER"', UI)

    def test_grid_vertical_rhythm_without_safearea_overrides(self):
        self.assertIn("alignment: .center, spacing: 28", UI)
        self.assertIn(".padding(.top, 16)", UI)

    def test_native_catalog_and_guest_ownership_preserved(self):
        self.assertIn('"SCARLET_DEVICE_MANAGED_IPA_SECTION"', UI)
        self.assertIn('"SCARLET_DEVICE_MANAGED_IPA_ROW"', UI)
        self.assertIn('"SCARLET_GUEST_LAUNCHER_TILE"', UI)
        self.assertIn('"SCARLET_APP_SEARCH"', UI)

if __name__ == "__main__":
    unittest.main()
