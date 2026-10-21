#!/usr/bin/env python3
"""V6: fix isolated xtool 1.22.2 developer portal identity mismatch.

After successful GrandSlam apptokens, /services/QH65B2/listTeams.action
previously used Pixel client info and unrelated Xcode version. Align with
Windows Anisette v3 used by successful SRP + 2FA; log token age band and
result code only. Never expose token, user ID, device ID, credentials, headers.
No login, signing, revocation, or installation performed by this patch.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

PIN="65bf3cc5a1240fea53ac0748d29a01878222a6ce"
MARKER="NRG_XTOOL_DEVPORTAL_V6"
DEV=Path("Sources/XKit/DeveloperServices/DeveloperServicesClient.swift")
LOGIN=Path("Sources/XKit/DeveloperServices/DeveloperServicesLoginManager.swift")
AUTH=Path("Sources/XToolSupport/AuthCommand.swift")

PATCHES={
DEV: [
("""        anisetteData.dictionary.forEach { httpRequest.headerFields[.init($0)!] = $1 }

        request.configure(urlRequest: &httpRequest)""",
"""        anisetteData.dictionary.forEach { httpRequest.headerFields[.init($0)!] = $1 }

        // NRG_XTOOL_DEVPORTAL_V6: GSA and Developer Services must describe
        // the SAME Windows Anisette identity. The upstream default describes
        // a Pixel and an unrelated Xcode release despite Windows-ADI tokens.
        // Scope only to the opt-in, isolated SideInstaller compatibility mode.
        if DeviceInfo.nrgSideStoreAuth {
            httpRequest.headerFields[.init(DeviceInfo.clientInfoKey)!] =
                DeviceInfo.nrgWindowsClientInfo
            httpRequest.headerFields[.init(DeviceInfo.xcodeVersionKey)!] =
                "14.2 (14C18)"
            httpRequest.headerFields[.acceptLanguage] = "en-us"
            httpRequest.headerFields[.init("Connection")!] = "close"
        }

        request.configure(urlRequest: &httpRequest)""")
],
LOGIN: [
("""        guard let token = tokens[.xcode]
            else { throw Error.missingLoginToken }
        return .init(adsid: loginData.adsid, token: token.value, expiry: token.expiry)""",
"""        guard let token = tokens[.xcode]
            else { throw Error.missingLoginToken }
        // NRG_XTOOL_DEVPORTAL_V6: report expiry state without timestamp,
        // token value, account name, or any secret metadata.
        if DeviceInfo.nrgSideStoreAuth,
           ProcessInfo.processInfo.environment["NRG_XTOOL_AUTH_TRACE"] == "1" {
            let seconds = token.expiry.timeIntervalSinceNow
            let expiryState = seconds <= 0 ? "expired" :
                seconds < 120 ? "near_expiry" : "valid"
            print("[NRG_AUTH_TRACE] phase=apptokens token_expiry=\\(expiryState)")
        }
        return .init(adsid: loginData.adsid, token: token.value, expiry: token.expiry)""")
],
AUTH: [
("""        let teams = try await client.send(DeveloperServicesListTeamsRequest())
        let team = try await Console.choose(""",
"""        // NRG_XTOOL_DEVPORTAL_V6: safe phase-only diagnostics. 1100 here is
        // the Developer Services response, not GrandSlam credentials or 2FA.
        let teams: [DeveloperServicesTeam]
        do {
            teams = try await client.send(DeveloperServicesListTeamsRequest())
            if ProcessInfo.processInfo.environment["NRG_XTOOL_SIDESTORE_AUTH"] == "1",
               ProcessInfo.processInfo.environment["NRG_XTOOL_AUTH_TRACE"] == "1" {
                print("[NRG_AUTH_TRACE] phase=listTeams result=ok")
            }
        } catch let e as DeveloperServicesAPIVersionLegacy.Error {
            if ProcessInfo.processInfo.environment["NRG_XTOOL_SIDESTORE_AUTH"] == "1",
               ProcessInfo.processInfo.environment["NRG_XTOOL_AUTH_TRACE"] == "1" {
                print("[NRG_AUTH_TRACE] phase=listTeams api_code=\\(e.code)")
            }
            throw e
        }
        let team = try await Console.choose(""")
]}


def patch(old,pairs,where):
    result=old
    for before,after in pairs:
        if result.count(after)==1:
            continue
        if result.count(before)!=1:
            raise ValueError(f"{where}: missing/ambiguous pinned upstream anchor")
        result=result.replace(before,after,1)
    return result


def main():
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument("xtool_checkout",type=Path)
    a=arg.add_mutually_exclusive_group(required=True)
    a.add_argument("--apply",action="store_true")
    a.add_argument("--check",action="store_true")
    p=arg.parse_args()
    root=p.xtool_checkout.resolve()
    if not (root/".git").is_dir():
        arg.error("Expected isolated xtool source checkout")
    sha=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if sha!=PIN:
        arg.error("Only pinned xtool v1.22.2 source supported")
    if "NRG_XTOOL_SIDESTORE_AUTH_V1" not in (root/"Sources/XKit/GrandSlam/Anisette/DeviceInfo.swift").read_text():
        arg.error("Missing prerequisite V1 opt-in compatibility layer")
    result={}
    for rel,changes in PATCHES.items():
        target=root/rel
        before=target.read_text(encoding="utf-8")
        after=patch(before,changes,str(rel))
        if p.check and (before!=after or MARKER not in before):
            arg.error(f"{rel}: missing or partial V6 patch")
        result[target]=(before,after)
    if p.apply:
        for target,(before,after) in result.items():
            if before!=after: target.write_text(after,encoding="utf-8")
    for target,(before,after) in result.items():
        print("CHECK_OK" if p.check else "PATCHED" if before!=after else "ALREADY_PATCHED",target.relative_to(root))
    print("NRG_XTOOL_DEVPORTAL_V6_READY: no network or login performed")


if __name__=="__main__":
    main()
