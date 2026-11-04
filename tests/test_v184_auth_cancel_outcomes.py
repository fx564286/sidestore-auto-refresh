"""V184 regression: cancellation outcomes survive view dismissal without leaking secrets."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(label, filename):
    spec = importlib.util.spec_from_file_location(label, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v167 = load("v167_for_v184", "patch_v167_restore_ondevice_pairing.py")
v182 = load("v182_for_v184", "patch_v182_p00_auth_cancel_liveness.py")
v183 = load("v183_for_v184", "patch_v183_host_diagnostic_logs.py")
v184 = load("v184_cancel", "patch_v184_auth_cancel_outcomes.py")


class V184AuthCancelOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()
        original = v182.patch(base)
        original += "\n// Fixture from the original V167 pairing command.\n" + v167.METHOD
        cls.v183 = v183.patch(original)
        cls.patched = v184.patch(cls.v183)

    def test_idempotent_and_expected_count(self):
        self.assertEqual(v184.patch(self.patched), self.patched)
        self.assertEqual(self.patched.count(v184.MARK), 1)
        for name in ("auth.cancel_terminal", "auth.cancel_unconfirmed",
                     "auth.cancel_watchdog", "auth.cancel_transport_failed"):
            self.assertEqual(self.patched.count('"' + name + '"'), 1)

    def test_terminal_state_logged_in_store_not_view(self):
        start = self.patched.index("final class V3AuthStore")
        end = self.patched.index("struct V3SignInLink", start)
        store = self.patched[start:end]
        self.assertIn("cancellationConfirmed ? .authCancelTerminal : .authCancelUnconfirmed", store)
        self.assertIn("ScarletV183HostLog.record(.authCancelWatchdog)", store)
        self.assertIn("ScarletV183HostLog.record(.authCancelTransportFailed)", store)
        self.assertNotIn("await oldTask?.value", store)

    def test_signin_ui_preserved(self):
        # No settings, dock, glass buttons or auth presentation changes.
        ui = "\nstruct V3SignInLink: View"
        self.assertEqual(self.v183[self.v183.index(ui):],
                         self.patched[self.patched.index(ui):])

    def test_secret_values_never_enter_host_events(self):
        enum = self.patched[self.patched.index("enum ScarletV183Event"):
                            self.patched.index("@MainActor\nenum ScarletV183HostLog")]
        event_names = [line.split('=', 1)[1].strip().strip('"')
                       for line in enum.splitlines()
                       if line.strip().startswith("case ") and '=' in line]
        for secret in ("password", "token", "sessionid", "verificationcode",
                       "accountid", "credential"):
            self.assertTrue(all(secret not in name.lower() for name in event_names))

    def test_fails_closed_without_parent_patches(self):
        with self.assertRaises(ValueError):
            v184.patch("struct V3LogsView: View {}")
        with self.assertRaises(ValueError):
            v184.patch(self.v183.replace(
                '                cancellationConfirmed = oldSession == nil || serverTerminal',
                '                cancellationConfirmed = true'))


if __name__ == "__main__":
    unittest.main()
