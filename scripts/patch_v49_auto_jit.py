#!/usr/bin/env python3
"""V49: verified LC host auto-resume, safe LiveProcess PID handoff."""
from pathlib import Path
import sys

PATH = Path("LiveContainerSwiftUI/Views/AppList/LCAppListView.swift")
MARK = "NRG_V49_VERIFIED_AUTO_RESUME"
START = """import Combine
import SwiftUI
import UniformTypeIdentifiers
"""
REPLACE_START = """import Combine
import SwiftUI
import UniformTypeIdentifiers

// NRG_V49_VERIFIED_AUTO_RESUME: only the current host CS_DEBUGGED state may
// release the legacy JIT waiting sheet. A helper URL opening is never proof.
@_silgen_name("csops")
private func nrgV49CSOps(_ pid: Int32, _ ops: UInt32, _ addr: UnsafeMutableRawPointer,
                         _ size: Int) -> Int32

private func nrgV49HostIsDebugged() -> Bool {
    var flags: Int32 = 0
    let status = nrgV49CSOps(getpid(), 0, &flags, MemoryLayout<Int32>.size)
    return status == 0 && (flags & 0x10000000) != 0
}
"""
OLD = """        guard let result = await jitAlert.open(), result else {
            UserDefaults.standard.removeObject(forKey: "selected")
            enableJITTask.cancel()
            return
        }
        LCSharedUtils.launchToGuestApp(withClassicMode: classicMode)
"""
NEW = """        // NRG_V49_VERIFIED_AUTO_RESUME: StikDebug foreground round-trip may
        // finish successfully without the user ever pressing "Launch Now".
        // This checks the *host* process for legacy/classic launches only;
        // LiveProcess guests have their own PID and cannot use this signal.
        let verifiedReturn = Task { @MainActor in
            for _ in 0..<360 { // 90 s upper bound; no endless polling
                if Task.isCancelled { return }
                if jitAlert.show && nrgV49HostIsDebugged() {
                    jitLog += "[NRG_V49] Host CS_DEBUGGED verified; releasing waiting sheet. Guest JIT pool is not yet verified.\\n"
                    jitAlert.close(result: true)
                    return
                }
                try? await Task.sleep(nanoseconds: 250_000_000)
            }
            jitLog += "[NRG_V49] JIT not verified within 90 s; manual cancel remains available.\\n"
        }
        defer { verifiedReturn.cancel() }
        guard let result = await jitAlert.open(), result else {
            UserDefaults.standard.removeObject(forKey: "selected")
            enableJITTask.cancel()
            return
        }
        LCSharedUtils.launchToGuestApp(withClassicMode: classicMode)
"""
OLD_PID = """                let encoded = encodedData.map { "&script-data=\\($0)" } ?? ""
                if let url = URL(string: "stikjit://enable-jit?bundle-id=\\(Bundle.main.bundleIdentifier!)&pid=\\(pid)\\(encoded)") {
                    if jitEnabler == .StikJITLC {
"""
NEW_PID = """                // NRG_V49_PID_SAFE_HANDOFF: do not concatenate query strings
                // containing & / + / = from the app's JIT launch script.
                guard pid > 0, let hostID = Bundle.main.bundleIdentifier else {
                    errorInfo = "[NRG_V49] Missing running LiveProcess PID or host Bundle ID."
                    errorShow = true
                    return
                }
                var components = URLComponents()
                components.scheme = "stikjit"
                components.host = "enable-jit"
                components.queryItems = [
                    URLQueryItem(name: "bundle-id", value: hostID),
                    URLQueryItem(name: "pid", value: String(pid))
                ]
                if let script, !script.isEmpty {
                    components.queryItems?.append(URLQueryItem(name: "script-data", value: script))
                }
                guard let url = components.url else {
                    errorInfo = "[NRG_V49] Unable to build PID-targeted StikDebug URL."
                    errorShow = true
                    return
                }
                NSLog("[NRG_V49_PID_SAFE_HANDOFF] target_pid=%d host_id=%@ provider=%@ runtime_jit_unverified=1",
                      pid, hostID, String(describing: jitEnabler))
                do {
                    if jitEnabler == .StikJITLC {
"""
END_OLD = """                    } else {
                        UIApplication.shared.open(url)
                    }
                }
            }
        }
    }
"""
END_NEW = """                    } else {
                        UIApplication.shared.open(url, options: [:]) { accepted in
                            NSLog("[NRG_V49_PID_SAFE_HANDOFF] request_accepted=%d runtime_jit_unverified=1", accepted ? 1 : 0)
                            if !accepted {
                                Task { @MainActor in
                                    errorInfo = "[NRG_V49] StikDebug did not accept the PID request; install/select external StikDebug."
                                    errorShow = true
                                }
                            }
                        }
                    }
                }
            }
        }
    }
"""
def patch(s: str) -> str:
    if MARK in s:
        if s.count(MARK) != 2 or "NRG_V49_PID_SAFE_HANDOFF" not in s or "for _ in 0..<360" not in s:
            raise RuntimeError("partial V49 patch")
        return s
    for old,new in ((START,REPLACE_START),(OLD,NEW),(OLD_PID,NEW_PID)):
        if s.count(old)!=1: raise RuntimeError(f"V49 anchor count {s.count(old)}: {old[:55]!r}")
        s=s.replace(old,new,1)
    # Limit the closure replacement to jitLaunch(withPID), not any other open(URL).
    a=s.index("    func jitLaunch(withPID pid:")
    b=s.index("    func showRunWhenMultitaskAlert()", a)
    section=s[a:b]
    if section.count(END_OLD)!=1: raise RuntimeError("V49 PID ending anchor not unique")
    s=s[:a]+section.replace(END_OLD,END_NEW,1)+s[b:]
    return s

def main(root: Path) -> None:
    p=root/PATH
    before=p.read_text()
    after=patch(before)
    if patch(after)!=after: raise RuntimeError("not idempotent")
    if after!=before: p.write_text(after)
    print("[PASS] V49 host debugged auto-resume + PID-safe external handoff")

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: patch_v49_auto_jit.py <LiveContainer>")
    main(Path(sys.argv[1]))
