#!/usr/bin/env python3
"""NRG v3.1.0 independent, fail-closed GrandSlam + host auth-loop patch.

Targets the exact v3.1.0 embedded SideStore/SideSign checkout AFTER NRG's
patch_sidesign_2fa_state and patch_combined_service_startup transformations.
No credentials, certificates, pairings or device operations are performed.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

MARKER = 'NRG_GSA_RECOVERY_V1'
SIDE_PATH = Path('SideStore/Core/Operations/StandaloneOperations/SignInOperation.swift')
AUTH_PATH = Path('Sources/DeveloperPortal/Authentication.swift')
PORTAL_PATH = Path('Sources/DeveloperPortal/DeveloperPortalAPI.swift')
SIDE_REF = 'ff25922e5c13ccfafd83bda5092910d848ebd409'
SIGN_REF = 'a731c0d5a9a6617c7b385ae493e07ffb7f81cd5d'

class PatchError(ValueError): pass

def one(src: str, old: str, new: str, where: str) -> str:
    count = src.count(old)
    if count != 1:
        raise PatchError(f'{where}: source anchor expected exactly once; found {count}. No changes written.')
    return src.replace(old, new, 1)

def patch_side_sign(src: str) -> str:
    if MARKER in src:
        if src.count('NRG_GSA_RECOVERY_V1:') != 3:
            raise PatchError('Incomplete or foreign patch marker in SideSign')
        return src

    # A private helper used for GrandSlam only; the original anisette state
    # and its identity remain intact for provisioning and developer operations.
    helper = '''    // NRG_GSA_RECOVERY_V1: use Android AuthKit identity for Android ADI anisette; 2FA must match.
    // Do not mutate Anisette machine IDs or re-provision existing identities.
    private func nrgGrandSlamClientInfo(_ original: String) -> String {
        // NRG_GSA_80045_IDENTITY_V2: server reports a macOS/akd identity;
        // keep its Anisette telemetry unchanged, advertise Android AuthKit
        // consistently for both initial SRP and 2FA GrandSlam traffic.
        return "<Pixel 7> <Android;14;UQ1A.240205.002> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
    }

'''
    src = one(src, 'public extension DeveloperPortal {\n', 'public extension DeveloperPortal {\n\n' + helper, 'GSA scoped client-info helper')
    src = one(src,
        '            "X-MMe-Client-Info": anisetteData.clientInfo,\n',
        '            "X-MMe-Client-Info": nrgGrandSlamClientInfo(anisetteData.clientInfo),\n',
        'GSA request header')

    # Early HTTP status classification. The existing upstream parser otherwise
    # attempts to interpret a proxy HTML 503 response as a plist and displays
    # generic incorrect-credentials-like errors. Never log raw response bytes.
    src = one(src,
        '        let statusCode = httpResponse?.statusCode ?? 0\n\n        guard !data.isEmpty else {',
        '''        let statusCode = httpResponse?.statusCode ?? 0

        // NRG_GSA_RECOVERY_V1: fail once; transport failure is not a bad password.
        if statusCode == 503 || statusCode == 429 {
            debugLog("[NRG_GSA] classified transport status=\\(statusCode)")
            throw ServerError.underlyingError(
                code: statusCode, message: "NRG_GSA_HTTP_\\(statusCode)")
        }

        guard !data.isEmpty else {''', 'GSA 503/429 response classification')

    # Apple can issue a trusted-device code unprompted with hsc 409 and au=nil.
    # Prevent the old pinned client from incorrectly proceeding to apptokens.
    src = one(src,
        '''        let authType = (statusDictionary?["au"] as? String)
           ?? (completeResponseDictionary["au"] as? String)''',
        '''        let authType = (statusDictionary?["au"] as? String)
           ?? (completeResponseDictionary["au"] as? String)
           ?? ((statusDictionary?["hsc"] as? Int) == 409 ? "NRGPushedCode" : nil)''',
        'GSA hsc409 classification')
    src = one(src,
        '''            case "trustedDeviceSecondaryAuth", "trustedDevice", "secondaryAuth", "sms", "voice", "phone":
                let isTrustedDevice = (authType == "trustedDeviceSecondaryAuth" || authType == "trustedDevice")''',
        '''            case "trustedDeviceSecondaryAuth", "trustedDevice", "secondaryAuth", "sms", "voice", "phone", "NRGPushedCode":
                let alreadySent = authType == "NRGPushedCode"
                if alreadySent && NRGPushedCodeCycle.handled {
                    throw DeveloperPortalError.requiresTwoFactorAuthentication
                }
                let isTrustedDevice = alreadySent || (authType == "trustedDeviceSecondaryAuth" || authType == "trustedDevice")''',
        'pushed-device challenge handling')
    src = one(src,
        '''                    verificationHandler: verificationHandler
                )
                // recur coz''',
        '''                    verificationHandler: verificationHandler,
                    codeAlreadySent: alreadySent
                )
                // recur coz''', 'pushed-code handler argument')
    src = one(src,
        '''                return try await authenticate(
                    appleID: unsanitizedAppleID,''',
        '''                return try await NRGPushedCodeCycle.$handled.withValue(
                    NRGPushedCodeCycle.handled || alreadySent
                ) {
                    try await authenticate(
                    appleID: unsanitizedAppleID,''', 'pushed-code recursion scope')
    src = one(src,
        '''                    verificationHandler: verificationHandler
                )

            case "repair":''',
        '''                    verificationHandler: verificationHandler
                    )
                }

            case "repair":''', 'pushed-code recursion closure')
    src = one(src,
        '''                            context: TwoFactorAuthContext,
                            verificationHandler: VerificationHandler?) async throws''',
        '''                            context: TwoFactorAuthContext,
                            verificationHandler: VerificationHandler?,
                            codeAlreadySent: Bool = false) async throws''', 'handle2FARequest signature')
    src = one(src,
        '''        var currentRequest: TwoFactorRequest = .selectDeliveryMethod(
            preferredMode: preferredMode,
            phoneNumbers: phoneNumbers
        )
        var activeChannel: TwoFactorAuthChannel? = nil''',
        '''        // NRG_GSA_RECOVERY_V1: no duplicate trusted-device code request.
        var currentRequest: TwoFactorRequest = codeAlreadySent
            ? .trustedDevice(error: nil)
            : .selectDeliveryMethod(preferredMode: preferredMode, phoneNumbers: phoneNumbers)
        var activeChannel: TwoFactorAuthChannel? = codeAlreadySent ? .trustedDevice : nil''',
        'already-sent 2FA prompt initial state')

    src = one(src, 'import GSACryptoKit\n', '''import GSACryptoKit

private enum NRGPushedCodeCycle {
    @TaskLocal static var handled = false
}
''', 'bounded 2FA recursion')
    src = one(src, 'codeAlreadySent: Bool = false) async throws \n',
              'codeAlreadySent: Bool = false) async throws\n',
              'SideSign 2FA trailing whitespace')
    return src


def patch_signin(src: str) -> str:
    """Patch NRG-generated SignInOperation, NOT pristine SideStore.

    NRG patch_v3_service.py already owns the credential transaction and removes
    destructive sign-out on failure. Add a terminal policy-error branch to
    its existing classified retry loop, preserving all original decisions.
    """
    if MARKER in src:
        if src.count(MARKER) != 1 or 'V3_AUTH_FAILURE_PRESERVES_ACCOUNT_STATE_V1' not in src:
            raise PatchError('Unexpected NRG generated sign-in marker')
        return src
    expected=('V3_PROVISIONING_RETRY_BYPASSES_CACHED_SIGNIN_V1',
              'V3_AUTH_FAILURE_PRESERVES_ACCOUNT_STATE_V1',
              'V3_AUTH_CREDENTIAL_TRANSACTION_V1',
              'v3ClassifyAuthError(error)',
              'V3TwoFactorRetryPolicy.shouldReuseCredentialsForCodeRetry')
    if any(token not in src for token in expected):
        raise PatchError('Expected post-NRG generated SignInOperation; original or drifted source refused.')
    if 'AuthManager.shared.signOut()' in src:
        raise PatchError('NRG generated SignInOperation unexpectedly contains signOut()')

    # A transport status invalidates this attempt, not the user's credentials.
    src = one(src,
        '                self.debugLog("[SignInOperation] Token authentication failed: \\(error)")',
        '''                if case ServerError.underlyingError(let code, _) = error,
                   code == 503 || code == 429 || code == -80045 || code == -22411 {
                    self.debugLog("[NRG_AUTH] silent_token_transport_status=\\(code)")
                    throw error
                }
                self.debugLog("[NRG_AUTH] silent_token_other_failure")''',
        'NRG silent token auth branch')
    src = one(src,
        '                self.debugLog("[SignInOperation] Saved password authentication failed: \\(error)")',
        '''                if case ServerError.underlyingError(let code, _) = error,
                   code == 503 || code == 429 || code == -80045 || code == -22411 {
                    self.debugLog("[NRG_AUTH] silent_password_transport_status=\\(code)")
                    throw error
                }
                self.debugLog("[NRG_AUTH] silent_password_other_failure")''',
        'NRG silent password auth branch')

    # This generated callback already handles user cancellation and 2FA code
    # retry. Insert ahead of v3ClassifyAuthError; never replace its loop.
    src = one(src,
        '''            } catch {
                if self.isCancelled || error is CancellationError || v3ClassifyAuthError(error) == nil {
                    throw OperationError.cancelled
                }
                self.debugLog("[V3_AUTH] attempt_failed")''',
        '''            } catch {
                // NRG_GSA_RECOVERY_V1: Apple policy/transport errors require
                // a new deliberate attempt; never request the password again.
                if case ServerError.underlyingError(let code, _) = error,
                   code == 503 || code == 429 || code == -80045 || code == -22411 {
                    self.debugLog("[NRG_AUTH] terminal_transport_status=\\(code)")
                    await handler.handleSignInResult(.failure(error))
                    throw error
                }
                if self.isCancelled || error is CancellationError || v3ClassifyAuthError(error) == nil {
                    throw OperationError.cancelled
                }
                self.debugLog("[V3_AUTH] attempt_failed")''',
        'NRG generated credential retry classifier')
    return src


def patch_portal(src: str) -> str:
    """Detect capacity failures in both portal v1 + services APIs.

    Does not revoke certificates, delete app IDs, retry a rejected request,
    or expose Apple response bodies in diagnostic logs.
    """
    marker='NRG_PROVISION_QUOTA_V1'
    if marker in src:
        if src.count(marker)!=2:
            raise PatchError('Incomplete NRG provisioning guard')
        return src
    boundary='    func sendServicesRequest<T: Decodable>('
    if src.count(boundary)!=1:
        raise PatchError('Unexpected SideSign DeveloperPortalAPI boundary')
    legacy,services=src.split(boundary,1)
    old='            if let code = status.resultCode, code != DeveloperPortalResultCodes.success {\n'
    insert='''            if let code = status.resultCode, code != DeveloperPortalResultCodes.success {
                // NRG_PROVISION_QUOTA_V1: App ID exhaustion is not an auth error.
                if code == 9120 {
                    debugLog("[NRG_PROVISION] app_id_quota code=9120")
                    throw DeveloperPortalError.maximumAppIDLimitReached(
                        cause: "Apple App ID capacity reached. Keep existing certificates and app data; wait for an App ID slot to become available.")
                }
'''
    legacy=one(legacy,old,insert,'legacy provisioning code=9120')
    services=one(services,old,insert,'services provisioning code=9120')
    return legacy+boundary+services

def git_head(path: Path) -> str | None:
    try:
        proc=subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],capture_output=True,text=True,timeout=5)
        return proc.stdout.strip() if proc.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):return None


def apply(side: Path, sidesign: Path, *, dry_run: bool=False, require_pins: bool=True) -> dict:
    side=side.expanduser().resolve()
    sidesign=sidesign.expanduser().resolve()
    targets=[side / SIDE_PATH,sidesign / AUTH_PATH,sidesign / PORTAL_PATH]
    if require_pins:
        for directory,expected in ((side,SIDE_REF),(sidesign,SIGN_REF)):
            actual=git_head(directory)
            if actual != expected:
                raise PatchError(f'Expected pinned repo commit {expected} at {directory}, found {actual!r}.')
    for target in targets:
        if not target.is_file() or target.is_symlink():
            raise PatchError(f'Missing or symlinked source: {target}')
    before=[f.read_text(encoding='utf-8') for f in targets]
    new=[patch_signin(before[0]),patch_side_sign(before[1]),patch_portal(before[2])]
    result={str(targets[i]):{'before_sha256':hashlib.sha256(before[i].encode()).hexdigest(),
       'after_sha256':hashlib.sha256(new[i].encode()).hexdigest(),
       'changed':new[i]!=before[i]} for i in range(3)}
    if dry_run:return result
    # All source guards validated before any file is written. Use temp+replace.
    for target,content,old in zip(targets,new,before):
        if content==old:continue
        stat=target.stat()
        if target.read_text(encoding='utf-8')!=old:
            raise PatchError(f'Source changed during patch: {target}')
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=target.parent,
                   prefix=f'.{target.name}.nrg-',delete=False) as fd:
            tmp=Path(fd.name);fd.write(content)
        os.chmod(tmp,stat.st_mode&0o777)
        os.replace(tmp,target)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('side',type=Path,help='NRG embedded SideStore checkout')
    p.add_argument('--sidesign',type=Path,help='Exact pinned SideSign submodule')
    p.add_argument('--check',action='store_true',help='Preflight without writes')
    a=p.parse_args(argv)
    sidesign=a.sidesign or a.side/'Dependencies/SideSign'
    try: result=apply(a.side,sidesign,dry_run=a.check)
    except (PatchError, OSError) as exc:
        print('NRG_GSA_PATCH_FAIL:',exc,file=sys.stderr)
        return 2
    for f,data in result.items():print(f'NRG_GSA_PATCH_OK {f} changed={data["changed"]} sha256={data["after_sha256"]}')
    return 0

if __name__=='__main__':raise SystemExit(main())
