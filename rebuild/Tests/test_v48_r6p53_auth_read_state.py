"""Execute the production auth read state/coordinator, not a Python surrogate."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
X = (ROOT / "HostApp/ScarletAuthXPCSupport.swift").read_text()
W = (ROOT / "integration/wire_scarlet_auth.py").read_text()
H = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
A = (ROOT / "HostApp/ScarletAutomaticRenewal.swift").read_text()
class AuthReadState(unittest.TestCase):
    def test_unavailable_cannot_be_reported_as_missing_or_authorize_refresh(self):
        read = X.split("public func storedAuthenticationState()", 1)[1].split(
            "public func signIn(", 1)[0]
        self.assertIn('gate.finish(.unavailable(reason: "auth_state_read_timeout"))', read)
        self.assertIn("if case .unavailable = state { isReady = false }", read)
        self.assertIn("remote.scarletAuthStoredState", read)
        self.assertNotIn("gate.finish(false)", read)
        self.assertIn("await storedAuthenticationState().isAuthenticated", X)
        self.assertIn("if let verified = stored.verifiedValue", H)
        self.assertIn('"host_session_read_unavailable"', H)
        self.assertLess(A.index('"automatic_deferred_auth_read"'),
                        A.index("guard authState.isAuthenticated else"))
        self.assertIn('"auth_state_unavailable"', A)
        self.assertIn("reply(2);", W)
        self.assertIn("reply(authenticated ? 1 : 0);", W)
    def test_actual_swift_states_coalescing_stale_invalidation_and_single_resume(self):
        swift = shutil.which("swiftc")
        if not swift: self.skipTest("Swift compiler available in native Xcode CI")
        source = X.split("// R6P53_STORED_AUTH_STATE_BEGIN", 1)[1].split(
            "// R6P53_STORED_AUTH_STATE_END", 1)[0]
        checks = r"""
@main struct Test {
    @MainActor static func main() async {
        precondition(ScarletStoredAuthState.fromWorker(1).isAuthenticated)
        precondition(ScarletStoredAuthState.fromWorker(0) == .missing)
        for value in [-10, 2, 3, 1000] {
            let state = ScarletStoredAuthState.fromWorker(value)
            precondition(!state.isAuthenticated && state.verifiedValue == nil)
            precondition(state.failureReason == "auth_state_unavailable")
        }
        let reads = ScarletStoredAuthReads()
        var calls = 0
        var resumeFirst: CheckedContinuation<ScarletStoredAuthState, Never>?
        let first = Task { @MainActor in
            await reads.read {
                calls += 1
                return await withCheckedContinuation { resumeFirst = $0 }
            }
        }
        while resumeFirst == nil { await Task.yield() }
        var secondEntered = false
        let second = Task { @MainActor in
            secondEntered = true
            return await reads.read { calls += 1; return .missing }
        }
        while !secondEntered { await Task.yield() }
        resumeFirst!.resume(returning: .authenticated)
        let a = await first.value, b = await second.value
        precondition(a == .authenticated && b == .authenticated && calls == 1)
        let fresh = await reads.read { calls += 1; return .missing }
        precondition(fresh == .missing && calls == 2) // no cached positive
        var staleResume: CheckedContinuation<ScarletStoredAuthState, Never>?
        let stale = Task { @MainActor in
            await reads.read {
                await withCheckedContinuation { staleResume = $0 }
            }
        }
        while staleResume == nil { await Task.yield() }
        reads.invalidate()
        var newResume: CheckedContinuation<ScarletStoredAuthState, Never>?
        let newer = Task { @MainActor in
            await reads.read {
                await withCheckedContinuation { newResume = $0 }
            }
        }
        while newResume == nil { await Task.yield() }
        staleResume!.resume(returning: .missing)
        let outdated = await stale.value
        precondition(outdated == .unavailable(reason: "auth_changed_during_read"))
        var followerEntered = false
        let follower = Task { @MainActor in
            followerEntered = true
            return await reads.read { fatalError("old read erased the new pending read") }
        }
        while !followerEntered { await Task.yield() }
        newResume!.resume(returning: .authenticated)
        let n = await newer.value, f = await follower.value
        precondition(n == .authenticated && f == .authenticated)
        var gate: ScarletStoredAuthGate?
        let timeout = Task { @MainActor in
            await withCheckedContinuation { gate = ScarletStoredAuthGate($0) }
        }
        while gate == nil { await Task.yield() }
        gate!.finish(.unavailable(reason: "auth_state_read_timeout"))
        gate!.finish(.authenticated) // duplicate late callback must not resume
        let timed = await timeout.value
        precondition(timed == .unavailable(reason: "auth_state_read_timeout"))
        print("AUTH_STATE_PASS")
    }
}
"""
        with tempfile.TemporaryDirectory() as folder:
            src = Path(folder)/"Auth.swift"; out = Path(folder)/"test"
            src.write_text("import Foundation\n"+source+"\n"+checks)
            built = subprocess.run([swift, "-parse-as-library", str(src), "-o", str(out)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(out)], capture_output=True, text=True, timeout=20)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertIn("AUTH_STATE_PASS", ran.stdout)
if __name__ == "__main__": unittest.main()
