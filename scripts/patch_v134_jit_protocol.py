#!/usr/bin/env python3
"""V134: correct StikDebug script protocol and JIT claim semantics.

Never equate helper deep-link acceptance, debugApp return, or SideJITServer
trigger with executable JIT readiness. iOS 27 TXM JIT requires guest engine
support for its own executable-region breakpoint protocol.
"""
from pathlib import Path
import sys

APP = Path("LiveContainerSwiftUI/Views/AppList/LCAppListView.swift")
UTIL = Path("LiveContainerSwiftUI/Utilities/LCUtilsExtensions.swift")
MODEL = Path("LiveContainerSwiftUI/Models/LCAppModel.swift")
MARK = "SCARLET_V134_JIT_PROTOCOL"

def once(source: str, old: str, new: str, label: str):
    n=source.count(old)
    if n!=1:raise ValueError(f"V134 {label} anchor count={n}")
    return source.replace(old,new,1)

def app_patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'script-name' not in s:
            raise ValueError("V134 partial LiveProcess patch")
        return s
    if "SCARLET_V129_JIT_PREFLIGHT" not in s:
        raise ValueError("V129 PID preflight missing")
    anchor='''                if let script, !script.isEmpty {
                    components.queryItems?.append(URLQueryItem(name: "script-data", value: Data(script.utf8).base64EncodedString()))
                }'''
    new='''                // SCARLET_V134_JIT_PROTOCOL: script-name is NOT script-data.
                // The app model's JIT launch script may be either an actual
                // JavaScript body or a known built-in script filename.
                // Never send base64("universal.js") as executable JavaScript.
                if let script, !script.isEmpty {
                    let scriptInput = script.trimmingCharacters(in: .whitespacesAndNewlines)
                    if scriptInput == "universal.js" || scriptInput == "legacy.js" {
                        components.queryItems?.append(URLQueryItem(name: "script-name", value: scriptInput))
                        NSLog("[SCARLET_V134_JIT] route=liveprocess script=builtin_name runtime_verified=0")
                    } else {
                        components.queryItems?.append(URLQueryItem(name: "script-data",
                            value: Data(script.utf8).base64EncodedString()))
                        NSLog("[SCARLET_V134_JIT] route=liveprocess script=custom_data runtime_verified=0")
                    }
                } else if #available(iOS 26.0, *) {
                    NSLog("[SCARLET_V134_JIT] route=liveprocess script=absent txm=unknown runtime_verified=0")
                }'''
    s=once(s,anchor,new,"PID script wire format")
    # The successful external open callback is not proof of CS_DEBUGGED or
    # the guest's TXM/SPTM executable memory preparation.
    return once(s,
        '''NSLog("[NRG_V49_PID_SAFE_HANDOFF] request_accepted=%d runtime_jit_unverified=1", accepted ? 1 : 0)''',
        '''NSLog("[NRG_V49_PID_SAFE_HANDOFF] request_accepted=%d runtime_jit_unverified=1 txm_regions_unverified=1", accepted ? 1 : 0)''',
        "JIT handoff outcome")
def util_patch(s):
    mark="SCARLET_V134_CLASSIC_JIT_PROTOCOL"
    if mark in s:
        if s.count(mark)!=1 or '"script-name"' not in s:
            raise ValueError("V134 partial classic patch")
        return s
    if "SCARLET_V129_CLASSIC_JIT_ROUTE" not in s:
        raise ValueError("V129 classic JIT missing")
    anchor='''            if let script = script, !script.isEmpty {
                request.queryItems?.append(
                    URLQueryItem(name: "script-data", value: Data(script.utf8).base64EncodedString())
                )
            }'''
    new='''            // SCARLET_V134_CLASSIC_JIT_PROTOCOL: built-in script filename
            // and JavaScript source require DIFFERENT StikDebug query keys.
            // An external URL launch is only a request, never JIT readiness.
            if let script = script, !script.isEmpty {
                let input = script.trimmingCharacters(in: .whitespacesAndNewlines)
                if input == "universal.js" || input == "legacy.js" {
                    request.queryItems?.append(URLQueryItem(name: "script-name", value: input))
                    onServerMessage?("[V134 JIT] Built-in debugger script requested; JIT not yet verified.")
                } else {
                    request.queryItems?.append(
                        URLQueryItem(name: "script-data", value: Data(script.utf8).base64EncodedString())
                    )
                    onServerMessage?("[V134 JIT] Custom debugger script requested; JIT not yet verified.")
                }
            } else if #available(iOS 26.0, *) {
                onServerMessage?("[V134 JIT] No script configured. On TXM devices the target JIT engine must support an executable-region breakpoint protocol; debugger attachment alone is insufficient.")
            }'''
    s=once(s,anchor,new,"classic script query type")
    return once(s,
        '''                onServerMessage?("JIT acquisition will continue in StikDebug.")''',
        '''                onServerMessage?("[V134 JIT] StikDebug request sent; return and verify debugger, TXM memory preparation and guest execution. Request acceptance is not JIT success.")''',
        "classic outcome label")
def model_patch(s):
    mark="SCARLET_V134_JIT_PENDING"
    if mark in s:
        if s.count(mark)!=1:raise ValueError("V134 duplicate pending log")
        return s
    anchor='''                            continuation.resume()
                        }
                    }
                }
            } else {'''
    return once(s,anchor,
        '''                            // SCARLET_V134_JIT_PENDING: dispatching a
                            // StikDebug URL cannot prove that the guest's
                            // debugger attached or executable RX regions are
                            // ready under iOS 27 TXM. Never log enabled here.
                            NSLog("[SCARLET_V134_JIT] stage=handoff_returned pid=%d status=pending_external_verification",
                                  pidNumber.intValue)
                            continuation.resume()
                        }
                    }
                }
            } else {''',
        "LiveProcess pending (do not claim ready)")
def apply(root:Path):
    planned=[]
    for rel,fn in ((APP,app_patch),(UTIL,util_patch),(MODEL,model_patch)):
        p=root/rel
        if not p.is_file() or p.is_symlink():raise ValueError("V134 source unavailable "+str(rel))
        old=p.read_text()
        new=fn(old)
        if fn(new)!=new:raise ValueError("V134 not idempotent")
        planned.append((p,old,new))
    for p,old,new in planned:
        if old!=new:p.write_text(new)
    print("[PASS] V134 JIT script-name/custom-data protocol; handoff is pending, never claimed enabled")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v134_jit_protocol.py <LiveContainer root>")
    apply(Path(sys.argv[1]))
