#!/usr/bin/env python3
"""V47: use paired local debugger when SideJIT server is transiently unavailable.

V46 already handles empty server and network URLErrors. This closes the gap
where a discovered server responds with gateway errors 502/503/504. Other HTTP
and authorization errors retain the original error path. Neither LLDB attach
nor return from debugApp is treated as independent runtime-JIT proof.
"""
from pathlib import Path
import sys

MARK = "NRG_V47_JIT_GATEWAY_FALLBACK"
REL = Path("SideStore/Core/Operations/StandaloneOperations/EnableJITOperation.swift")
ANCHOR = '''                if let serverError = error as? SideJITServerErrorType {
                    switch serverError {'''
REPLACE = '''                // NRG_V47_JIT_GATEWAY_FALLBACK: the optional proxy may be
                // discoverable but unhealthy. Prefer already-paired local
                // debugger only for gateway/unavailable responses.
                if let gateway = error as? SideJITServerErrorType {
                    if case .other(let message) = gateway,
                       ["SideJITServer HTTP 502", "SideJITServer HTTP 503",
                        "SideJITServer HTTP 504"].contains(message) {
                        self.debugLog("[NRG_V47_JIT] gateway_unavailable fallback=paired_debugger")
                        try await debugApp(targetBundleId)
                        self.debugLog("[NRG_V47_JIT] debug_command_complete runtime_jit_unverified=1")
                        return
                    }
                }
                if let serverError = error as? SideJITServerErrorType {
                    switch serverError {'''

def patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or "runtime_jit_unverified=1" not in source:
            raise RuntimeError("V47 JIT fallback partial")
        return source
    if "NRG_V46_JIT_RECOVERY" not in source:
        raise RuntimeError("V47 JIT fallback requires V46")
    if source.count(ANCHOR) != 1:
        raise RuntimeError(f"V47 JIT catch anchor count {source.count(ANCHOR)}")
    return source.replace(ANCHOR, REPLACE, 1)

def main(root: Path) -> None:
    f = root / REL
    before = f.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise RuntimeError("V47 JIT transform non-idempotent")
    if after != before: f.write_text(after, encoding="utf-8")
    print("[PASS] V47 paired debugger fallback for 502/503/504; no false JIT success claim")

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("usage: patch_v47_jit_transport.py <pinned-EmbeddedSideStore>")
    main(Path(sys.argv[1]))
