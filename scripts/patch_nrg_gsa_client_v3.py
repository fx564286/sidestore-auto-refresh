#!/usr/bin/env python3
"""NRG GSA follow-up 2FA identity consistency, inspired by SideInstaller 56ecbf8."""
from __future__ import annotations
import argparse
from pathlib import Path
MARKER = "NRG_GSA_CLIENT_IDENTITY_V3"
REQUIRED = ("NRG_GSA_RECOVERY_V1", "NRG_GSA_HTTP_STATUS_V2", "nrgGrandSlamClientInfo")
RELATIVE = Path("Sources/DeveloperPortal/Authentication.swift")
START = "    private func makeTwoFactorAuthRequest("
BEFORE = '            "X-MMe-Client-Info": a.clientInfo,'
AFTER = ('            // NRG_GSA_CLIENT_IDENTITY_V3: SRP and 2FA use the same advertised identity.\n'
         '            // Leave Anisette identity, adi.pb, device ID and sessions untouched.\n'
         '            "X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo),')
def transform(source: str) -> str:
    if not all(token in source for token in REQUIRED):
        raise ValueError("V1/V2 source prerequisites missing")
    if source.count(START) != 1:
        raise ValueError("SideSign 2FA layout differs from pinned source")
    cut = source.index(START)
    tail = source[cut:]
    if MARKER in source:
        if source.count(MARKER) != 1 or tail.count(AFTER) != 1 or tail.count(BEFORE) != 0 or "NRG_GSA_WINDOWS_UA_V4" not in tail:
            raise ValueError("Partial V3 installation")
        return source
    if tail.count(BEFORE) != 1 or tail.count('"X-MMe-Client-Info"') != 1:
        raise ValueError("2FA request header source drift")
    new_tail = tail.replace(BEFORE, AFTER, 1)
    original_ua = '            "User-Agent": h.developerServices.userAgent,'
    replacement_ua = ('            // NRG_GSA_WINDOWS_UA_V4: align 2FA with PC AuthKit identity.\n'
                      '            "User-Agent": "akd/1.0 CFNetwork/808.1.4",')
    if new_tail.count(original_ua) != 1:
        raise ValueError("2FA User-Agent source drift")
    new_tail = new_tail.replace(original_ua, replacement_ua, 1)
    return source[:cut] + new_tail
def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply",action="store_true")
    group.add_argument("--check",action="store_true")
    a=p.parse_args()
    path=a.root/RELATIVE
    src=path.read_text()
    dst=transform(src)
    if a.check:
        if src != dst or src.count(MARKER)!=1: p.error("V3 is not fully installed")
        print("NRG_GSA_V3_CHECK_OK",path)
    elif dst != src:
        path.write_text(dst)
        print("NRG_GSA_V3_APPLIED",path)
    else: print("NRG_GSA_V3_ALREADY_APPLIED",path)
if __name__=="__main__": main()
