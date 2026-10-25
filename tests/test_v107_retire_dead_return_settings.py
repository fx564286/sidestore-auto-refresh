"""No resurrected settings for V105-deleted guest Return controls."""
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "remove_old_settings", ROOT / "scripts/patch_v107_retire_dead_return_settings.py")
v107 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v107)

OLD = """struct LCSettingsView: View {
    @AppStorage("LCHideReturnControl", store: UserDefaults.lcShared()) private var hideReturnControl = false
    @AppStorage("LCGuestReturnStartsCollapsed", store: UserDefaults.lcShared()) private var returnStartsCollapsed = false
    @AppStorage("LCGuestReturnCustomColors", store: UserDefaults.lcShared()) private var returnCustomColors = false
    @AppStorage("LCGuestReturnTintRGB", store: UserDefaults.lcShared()) private var returnTintRGB = 0x007AFF
    @AppStorage("LCGuestReturnBackgroundRGB", store: UserDefaults.lcShared()) private var returnBackgroundRGB = 0xF2F2F7
    @State var errorShow = false

    private func returnColorBinding(_ rgb: Binding<Int>) -> Binding<Color> {
        return Binding(get: { Color.red }, set: { _ in })
    }
    var body: some View {
        NavigationView {
            Form {
                V3AccountSettings()
                Section {
                    Toggle("Show Return Button", isOn: Binding(get: { !hideReturnControl }, set: { hideReturnControl = !$0 }))
                    Group {
                        Toggle("Start Collapsed", isOn: $returnStartsCollapsed)
                        Toggle("Use Custom Colors", isOn: $returnCustomColors)
                        if returnCustomColors {
                            ColorPicker("Button Background", selection: returnColorBinding($returnBackgroundRGB))
                        }
                    }
                } header: {
                    Text("Guest Controls")
                } footer: {
                    Text("Start Collapsed shows an edge tab when a guest opens")
                }
                Section {
                    NavigationLink { LCEmbeddedSideStoreRefreshView() } label: { Text("Refresh") }
                }
                NavigationLink { LCJITLessDiagnoseView() } label: { Text("JIT") }
            }
        }
    }
}
"""

class DeadReturnSettingTests(unittest.TestCase):
    def test_remove_entire_legacy_settings_UI_without_mutating_active_UI(self):
        s = v107.patch(OLD)
        self.assertEqual(s, v107.patch(s))
        self.assertIn(v107.MARK, s)
        for obsolete in v107.OLD_KEYS + v107.OLD_ROWS + ('returnColorBinding(',):
            self.assertNotIn(obsolete, s)
        for live in ('V3AccountSettings()', 'LCJITLessDiagnoseView()',
                     'LCEmbeddedSideStoreRefreshView()', 'NavigationView'):
            self.assertIn(live, s)

    def test_fail_closed_on_drift_or_half_migration(self):
        with self.assertRaises(ValueError):
            v107.patch(OLD.replace('LCGuestReturnCustomColors', 'renamedSetting'))
        with self.assertRaises(ValueError):
            v107.patch(OLD.replace('LCJITLessDiagnoseView()', 'removedLiveFeature'))
        patched = v107.patch(OLD)
        with self.assertRaises(ValueError):
            v107.patch(patched + 'LCGuestReturnStartsCollapsed')

    def test_isolated_file_patch_and_data_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / v107.SETTINGS
            p.parent.mkdir(parents=True)
            p.write_text(OLD)
            v107.apply(root)
            v107.apply(root)
            self.assertEqual(p.read_text(), v107.patch(OLD))
        source = (ROOT / "scripts/patch_v107_retire_dead_return_settings.py").read_text()
        for dangerous in ('SecItemDelete(', 'removeObject(forKey:', 'removePersistentDomain(',
                          'removeItem(at:', 'launchToGuestAppWithClassicMode'):
            self.assertNotIn(dangerous, source)

    def test_generated_build_source(self):
        root = os.getenv("V107_PATCHED_LIVECONTAINER")
        if not root:
            # Pre-patch repository checks have no generated source. CI invokes
            # this test again with V107_PATCHED_LIVECONTAINER after migration.
            return
        source = (Path(root) / v107.SETTINGS).read_text()
        self.assertEqual(v107.patch(source), source)


if __name__ == "__main__":
    unittest.main()
