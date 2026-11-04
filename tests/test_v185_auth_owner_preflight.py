"""V185 regression: host-owned sign-in survives view navigation, rights checked."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(filename):
    spec=importlib.util.spec_from_file_location(filename.removesuffix(".py"),
                                                ROOT/"scripts"/filename)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v167=load("patch_v167_restore_ondevice_pairing.py")
v182=load("patch_v182_p00_auth_cancel_liveness.py")
v183=load("patch_v183_host_diagnostic_logs.py")
v184=load("patch_v184_auth_cancel_outcomes.py")
v185=load("patch_v185_auth_owner_preflight.py")


class V185AuthOwnerPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text()
        original=v182.patch(original)
        original+="\n// Restored V167 pairing workflow fixture.\n"+v167.METHOD
        cls.predecessor=v184.patch(v183.patch(original))
        cls.patched=v185.patch(cls.predecessor)

    def test_idempotent(self):
        self.assertEqual(v185.patch(self.patched),self.patched)
        self.assertEqual(self.patched.count(v185.MARK),1)

    def test_host_owned_store_not_view_state(self):
        cls=self.patched
        self.assertEqual(cls.count("static let shared = V3AuthStore()"),1)
        self.assertEqual(cls.count("@ObservedObject private var auth = V3AuthStore.shared"),1)
        self.assertNotIn("@StateObject private var auth = V3AuthStore()",cls)

    def test_appgroup_is_os_entitlement_preflight(self):
        src=self.patched
        assert 'SecTaskCopyValueForEntitlement(' in src
        assert '"com.apple.security.application-groups" as CFString' in src
        store=src[src.index("final class V3AuthStore"):src.index("struct V3SignInLink")]
        self.assertLess(store.index("guard Self.hasRequiredHostAppGroup"),
                        store.index('session = requestedSession'))
        self.assertIn("ScarletV183HostLog.record(.authAppGroupMissing)",store)
        self.assertNotIn("App Groups were restored",store)

    def test_auth_start_has_bounded_rpc_only(self):
        store=self.patched[self.patched.index("final class V3AuthStore"):
                           self.patched.index("struct V3SignInLink")]
        self.assertIn("requestDeadline: Date().addingTimeInterval(25)",store)
        self.assertIn("ScarletV183HostLog.record(.authBeginDispatched)",store)
        self.assertIn("ScarletV183HostLog.record(.authBeginAccepted)",store)
        self.assertIn("ScarletV183HostLog.record(.authBeginRequestFailed)",store)
        self.assertIn("try await pollLoop(id: id, sessionDeadline: sessionDeadline)",store)

    def test_no_secret_material_logged(self):
        pat=self.patched
        for event in ("auth.begin_dispatched","auth.begin_accepted",
                      "auth.begin_request_failed","auth.entitlement_app_group_missing"):
            self.assertEqual(pat.count('"'+event+'"'),1)
        changed=pat[len(self.predecessor):]
        self.assertNotIn("password =",changed)
        self.assertNotIn("accountID =",changed)
        self.assertNotIn("2FACode =",changed)

    def test_ui_preserved_except_auth_object_ownership(self):
        a=self.predecessor.replace("@StateObject private var auth = V3AuthStore()",
                                   "@ObservedObject private var auth = V3AuthStore.shared")
        begin="struct V3SignInLink: View"
        end="// SCARLET_V183_HOST_LOG_FALLBACK"
        self.assertEqual(a[a.index(begin):a.index(end)],
                         self.patched[self.patched.index(begin):self.patched.index(end)])

    def test_requires_v184(self):
        with self.assertRaisesRegex(ValueError,"requires V184"):
            v185.patch((ROOT/"scripts/templates/v3_unified_shell.swift").read_text())

if __name__=="__main__":
    unittest.main()
