#!/usr/bin/env python3
"""V43: DNS-SD descriptors must never fall through to ordinary DNS."""
from pathlib import Path
import sys
MARK = "NRG_V43_DNSSD_FAIL_CLOSED"
REL = Path("SideStore/Core/JIT/SideJITManager.swift")
def patch(s):
    if MARK in s:
        return s
    # Use stable statement matching without escaping interpolations.
    lines=s.splitlines(keepends=True)
    indices=[i for i,l in enumerate(lines) if 'DNS-SD resolution timed out for descriptor' in l]
    if len(indices)!=1: raise RuntimeError("Expected exactly one DNS-SD timeout branch")
    i=indices[0]
    lines.insert(i+1, '            // '+MARK+': do not DNS-resolve a Bonjour service descriptor.\\n'.replace('\\n','\n')+'            return nil\n')
    s=''.join(lines)
    # A nil fallback must not be turned back into the unsafe default URL.
    old='        return AppConstants.SideJIT.defaultServerURL\n'
    if s.count(old)!=1: raise RuntimeError("Expected one fallback return")
    s=s.replace(old, '        return "" // '+MARK+': unresolved server; do not trigger network requests.\n',1)
    # V44: unresolved user overrides and absent servers must fail closed.
    override = '            return userInput\n'
    if s.count(override) != 1:
        raise RuntimeError("Expected one raw override return")
    s = s.replace(override, '            return "" // NRG_V44 unresolved override\n', 1)
    trigger = '        let SJSURL = await resolveServerURL()\n'
    if s.count(trigger) != 2:
        raise RuntimeError("Expected two SideJIT URL call sites")
    s = s.replace(trigger, trigger +
        '        guard !SJSURL.isEmpty else {\n' +
        '            debugLog("[SideJITManager] NRG_V44: no server; skip trigger")\n' +
        '            return\n' +
        '        }\n', 1)
    return s
def main():
    root=Path(sys.argv[1]);f=root/REL;s=f.read_text();t=patch(s)
    if t!=s:f.write_text(t)
    assert MARK in t and 'return nil' in t
    print("[PASS] V43 DNS-SD fail-closed")
if __name__=="__main__":main()
