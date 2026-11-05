"""V189: cancellation intent survives watchdog and misordered authBegin RPC completion."""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(file):
    spec=importlib.util.spec_from_file_location(file[:-3],ROOT/"scripts"/file)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

v167=load("patch_v167_restore_ondevice_pairing.py")
v182=load("patch_v182_p00_auth_cancel_liveness.py")
v183=load("patch_v183_host_diagnostic_logs.py")
v184=load("patch_v184_auth_cancel_outcomes.py")
v185=load("patch_v185_auth_owner_preflight.py")
v186=load("patch_v186_auth_start_outcome.py")
v189=load("patch_v189_auth_cancel_intent.py")

class AuthCancelIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=(ROOT/"scripts/templates/v3_unified_shell.swift").read_text()
        prepared=v182.patch(base)
        prepared+="\n// V167 pairing fixture\n"+v167.METHOD
        cls.predecessor=v186.patch(v185.patch(v184.patch(v183.patch(prepared))))
        cls.updated=v189.patch(cls.predecessor)
        begin=cls.updated.index("    private func run(sessionID requestedSession: String) async {")
        end=cls.updated.index("    private func pollLoop(id:",begin)
        cls.begin=cls.updated[begin:end]
        cstart=cls.updated.index("    func cancel() {",end)
        cend=cls.updated.index("\n    }\n}",cstart)
        cls.cancel=cls.updated[cstart:cend]

    def test_idempotence_and_scope(self):
        self.assertEqual(v189.patch(self.updated),self.updated)
        self.assertEqual(self.updated.count(v189.MARK),1)
        self.assertEqual(self.predecessor[:self.predecessor.index("final class V3AuthStore:")],
                         self.updated[:self.updated.index("final class V3AuthStore:")])

    def test_record_cancellation_intent_before_task_cancel(self):
        self.assertIn("authBeginUserCancellationSessions.insert(pending)",self.cancel)
        self.assertLess(self.cancel.index("authBeginUserCancellationSessions.insert(pending)"),
                        self.cancel.index("task?.cancel()"))

    def test_remote_request_result_after_cancel_cannot_be_success(self):
        self.assertIn("authBeginUserCancellationSessions.contains(requestedSession)",self.begin)
        self.assertIn("throw CancellationError()",self.begin)
        self.assertIn("authBeginUserCancellationSessions.remove(requestedSession)",self.begin)

    def test_watchdog_may_clear_is_cancelling_but_intent_still_wins(self):
        self.assertIn("if userCancelIntent || isCancelling || Task.isCancelled || error is CancellationError",self.begin)
        self.assertIn("ScarletV183HostLog.record(.authBeginLocallyCancelled)",self.begin)
        self.assertIn("ScarletV183HostLog.record(.authBeginRequestFailed)",self.begin)

    def test_never_claim_server_cancel_terminal_on_local_intent(self):
        self.assertNotIn("authCancelTerminal",self.begin)
        self.assertNotIn("cancellationConfirmed = true",self.begin)
        self.assertNotIn("authBeginUserCancellationSessions.removeAll()",self.updated)

    def test_fails_closed_without_predecessor(self):
        with self.assertRaisesRegex(ValueError,"V186"):
            v189.patch((ROOT/"scripts/templates/v3_unified_shell.swift").read_text())

if __name__=="__main__":
    unittest.main()
