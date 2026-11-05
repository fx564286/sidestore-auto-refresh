"""Offline contract tests: iPhone dispatch cannot sign without owner validation."""
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"tools/scarlet_shortcut_sign_agent.py"
spec=importlib.util.spec_from_file_location("scarlet_agent",FILE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SigningDispatchSecurity(unittest.TestCase):
    def request(self, **changes):
        row={"id":123456,"event":"workflow_dispatch","head_branch":"main",
             "actor":{"login":"fx564286"},
             "head_repository":{"full_name":"fx564286/sidestore-auto-refresh"},
             "path":".github/workflows/scarlet-sign-request.yml"}
        row.update(changes)
        return row

    def test_only_owner_workflow_dispatch_is_accepted(self):
        self.assertTrue(mod.accepted(self.request()))
        for bad in (
            {"actor":{"login":"untrusted"}},
            {"event":"pull_request"},
            {"event":"push"},
            {"head_branch":"untrusted"},
            {"head_repository":{"full_name":"other/repo"}},
            {"path":".github/workflows/other.yml"},
        ):
            self.assertFalse(mod.accepted(self.request(**bad)))

    def test_owner_workflow_path_with_api_branch_suffix(self):
        self.assertTrue(mod.accepted(self.request(path=".github/workflows/scarlet-sign-request.yml@main")))
        self.assertTrue(mod.accepted(self.request(path=".github/workflows/scarlet-sign-request.yml")))
        for wrong in (
            ".github/workflows/scarlet-sign-request.yml@other",
            ".github/workflows/scarlet-sign-request.yml.backup@main",
            ".github/workflows/other/scarlet-sign-request.yml@main",
        ):
            self.assertFalse(mod.accepted(self.request(path=wrong)))

    def test_multiple_requests_use_latest_unique_run_id(self):
        with patch.object(mod,"gh",return_value={"workflow_runs":[self.request(id=1),self.request(id=3),self.request(id=2)]}):
            self.assertEqual(mod.latest_request()["id"],3)

    def test_empty_queue_no_sign(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(mod,"STATE",Path(d)),patch.object(mod,"LAST",Path(d)/"last.json"),patch.object(mod,"latest_request",return_value=None):
                with patch.object(mod,"ensure_publisher") as signing:
                    mod.once()
                    signing.assert_not_called()

    def test_rejected_actor_does_not_touch_signing(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(mod,"STATE",Path(d)),patch.object(mod,"LAST",Path(d)/"last.json"),patch.object(mod,"latest_request",return_value=self.request(actor={"login":"attacker"})):
                with patch.object(mod,"ensure_publisher") as signing:
                    mod.once()
                    signing.assert_not_called()
                    self.assertIn('"status": "rejected"',(Path(d)/"last.json").read_text())

    def test_successful_dispatch_invokes_real_local_signer(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(mod,"STATE",Path(d)),patch.object(mod,"LAST",Path(d)/"last.json"),patch.object(mod,"latest_request",return_value=self.request()):
                with patch.object(mod,"ensure_publisher") as prepare,patch.object(mod,"command",return_value=mod.INSTALL_URL+"\n") as exec_,patch.object(mod,"publish_status") as status:
                    mod.once()
                    prepare.assert_called_once()
                    self.assertEqual(exec_.call_args.args[0][0],"python3")
                    self.assertEqual(exec_.call_args.args[0][1],mod.PUBLISHER)
                    self.assertIn('"status": "published"',(Path(d)/"last.json").read_text())
                    self.assertEqual(status.call_args.args[1],"published")

    def test_failed_signing_is_not_claimed_success(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(mod,"STATE",Path(d)),patch.object(mod,"LAST",Path(d)/"last.json"),patch.object(mod,"latest_request",return_value=self.request()):
                with patch.object(mod,"ensure_publisher"),patch.object(mod,"command",side_effect=RuntimeError("blocked")),patch.object(mod,"publish_status") as status:
                    mod.once()
                    self.assertIn('"status": "failed"',(Path(d)/"last.json").read_text())
                    self.assertEqual(status.call_args.args[1],"failed")

    def test_never_signs_in_github_or_revokes(self):
        text=FILE.read_text()
        self.assertIn("PUBLISHER_PIN",text)
        self.assertIn("LOCAL_APPLE_SIGNING_PUBLISH_COMPLETE",text)
        self.assertNotIn("revokeDevelopmentCert",text)
        self.assertNotIn("submitDevelopmentCSR",text)
        self.assertNotIn("sshpass",text)
        self.assertNotIn("192.168.50.",text)

if __name__=="__main__":
    unittest.main()
