#!/usr/bin/env python3
"""Experimental headless SideStore SignInOperation adapter.

No native SideStore login or 2FA window is presented. Uses original SideSign
operations, ephemeral NSXPC callbacks, and preserves existing signing assets
on failure. Deliberately skips certificate replacement, device registration,
and auto-resigning until explicitly verified on a signed iPhone.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

PIN="ee3cc16a67f9fed766f79a0ed70938f0f8ad5a07"
AUTH_REL="SideStore/Core/Auth/AuthManager.swift"
OPER_REL="SideStore/Core/Operations/StandaloneOperations/SignInOperation.swift"

ENGINE=r'''
// Scarlet's headless bridge to the ORIGINAL SignInOperation.
// The native SideStore AuthenticationViewController is never constructed.
@MainActor
final class ScarletHeadlessSignInHandler: SignInFlowHandler {
    private let appleID: String
    private let secret: String
    private let challenge: (NSString, @escaping (NSString?) -> Void) -> Void
    private var attempted = false
    private var lastSignInError: Error?

    init(appleID: String, password: String,
         challenge: @escaping (NSString, @escaping (NSString?) -> Void) -> Void) {
        self.appleID = appleID
        self.secret = password
        self.challenge = challenge
        super.init(presentingViewController: nil)
    }

    override func credentials() async throws -> (String, String) {
        if attempted {
            throw lastSignInError ?? OperationError.cancelled
        }
        attempted = true
        return (appleID, secret)
    }

    override func handleSignInResult(_ result: Result<(ALTAccount, ALTAppleAPISession), Error>) async {
        if case .failure(let error) = result {
            lastSignInError = error
        }
    }

    override func verificationCode(for request: TwoFactorRequest) async throws -> TwoFactorResponse {
        if case .selectDeliveryMethod(let mode, let phones) = request {
            switch mode {
            case .trustedDevice:
                return .requestTrustedDevice
            case .sms:
                guard phones.count == 1, let id = phones.first?.id else { return .cancel }
                return .requestSMS(phoneID: id)
            case .voice:
                guard phones.count == 1, let id = phones.first?.id else { return .cancel }
                return .requestVoice(phoneID: id)
            }
        }
        let prompt: String
        switch request {
        case .trustedDevice:
            prompt = "Apple 신뢰 기기에 표시된 6자리 인증번호"
        case .sms:
            prompt = "Apple SMS로 받은 6자리 인증번호"
        case .voice:
            prompt = "Apple 전화로 받은 6자리 인증번호"
        case .selectDeliveryMethod:
            return .cancel
        }
        let description = [prompt, request.error].compactMap { $0 }
            .filter { !$0.isEmpty }.joined(separator: " · ")
        return try await withCheckedThrowingContinuation {
            (continuation: CheckedContinuation<TwoFactorResponse, Error>) in
            challenge(description as NSString) { value in
                guard let code = value as String?,
                      code.utf8.count == 6,
                      code.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }) else {
                    continuation.resume(returning: .cancel)
                    return
                }
                continuation.resume(returning: .verificationCode(code))
            }
        }
    }

    override func resolveTeam(_ teams: [ALTTeam]) async throws -> ALTTeam {
        guard teams.count == 1, let team = teams.first else {
            throw OperationError.invalidParameters(
                "Multiple developer teams require explicit Scarlet team selection")
        }
        return team
    }

    override func accountRepair(url: URL, message: String) async -> AccountRepairDecision {
        return .cancel
    }

    override func warnOutdatedAnisetteServer() async throws -> Bool {
        throw OperationError.invalidParameters("Outdated Anisette source requires review")
    }
}

private extension AuthManager {
    func scarletHeadlessSignIn(handler: ScarletHeadlessSignInHandler) async throws -> SignInResult {
        let context = StandaloneOperationContext(
            steps: .signIn,
            dbBackgroundContext: DatabaseManager.shared.persistentContainer.newBackgroundContext()
        )
        let operation = try SignInOperation(
            context: context,
            signInHandler: handler,
            anisetteServerHandler: handler,
            skipDeviceRegistration: true,
            skipCertificateProvisioning: true,
            skipResign: true,
            skipHowTos: true
        )
        let result = try await operation.execute()
        self.team = result.team
        self.session = result.session
        return result
    }
}

@objc(ScarletSideStoreAuthEngine)
final class ScarletSideStoreAuthEngine: NSObject {
    typealias CodeReply = @convention(block) (NSString?) -> Void
    typealias Challenge = @convention(block) (NSString, CodeReply) -> Void

    @objc(beginAuthenticationWithAppleID:password:challenge:reply:)
    static func beginAuthentication(appleID: NSString,
                                    password: NSString,
                                    challenge: @escaping Challenge,
                                    reply: @escaping CodeReply) {
        Task { @MainActor in
            let handler = ScarletHeadlessSignInHandler(
                appleID: appleID as String,
                password: password as String,
                challenge: { prompt, done in
                    let block: CodeReply = { code in done(code) }
                    challenge(prompt, block)
                }
            )
            do {
                _ = try await AuthManager.shared.scarletHeadlessSignIn(handler: handler)
                reply(nil)
            } catch {
                // Never log/store credentials, verification codes, or tokens.
                reply(error.localizedDescription as NSString)
            }
        }
    }
}
'''

def modify_auth(src:str)->str:
    anchor='public final class AuthManager: @unchecked Sendable {'
    if src.count(anchor)!=1 or "scarletHeadlessSignIn" in src:
        raise RuntimeError("Pinned SideStore AuthManager changed")
    if "try await signInOperation.execute()" not in src:
        raise RuntimeError("Pinned original SignInOperation pipeline missing")
    return src+"\n"+ENGINE

def modify_operation(src:str)->str:
    old='''            if !AuthManager.shared.hasStoredPassword &&
               !AuthManager.shared.hasStoredXcodeToken
            {
                await AuthManager.shared.signOut()
            }
'''
    new='''            if !AuthManager.shared.hasStoredPassword &&
               !AuthManager.shared.hasStoredXcodeToken
            {
                // Scarlet's headless authentication must never revoke an
                // existing certificate because a remote attempt failed.
                // Native SideStore's original behavior remains unchanged.
                if !(self.signInHandler is ScarletHeadlessSignInHandler) {
                    await AuthManager.shared.signOut()
                }
            }
'''
    if src.count(old)!=1:raise RuntimeError("Original sign-out guard changed")
    return src.replace(old,new)

def sha(buf:bytes):return hashlib.sha256(buf).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--engine",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    a=args.engine/AUTH_REL;op=args.engine/OPER_REL
    assert a.is_file() and op.is_file(),"Pinned SideStore source missing"
    originalA=a.read_bytes();originalOp=op.read_bytes()
    updatedA=modify_auth(originalA.decode())
    updatedOp=modify_operation(originalOp.decode())
    a.write_text(updatedA);op.write_text(updatedOp)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({
        "upstreamPin":PIN,"engineUsed":"original SignInOperation/SideSign",
        "sideStoreAuthenticationWindowPresented":False,
        "secretURLStorageAllowed":False,
        "preservesOriginalCertificateOnFailedAttempt":True,
        "skipsCertificateAndDeviceProvisioningUntilVerified":True,
        "hostGuestXPCOnDeviceVerified":False,
        "files":{
            AUTH_REL:{"before":sha(originalA),"after":sha(updatedA.encode())},
            OPER_REL:{"before":sha(originalOp),"after":sha(updatedOp.encode())}
        }
    },indent=2)+"\n")
    print("[PASS] Headless research adapter compiled from original SideStore authentication engine")
    print("[BLOCK] Real login, certificate/profile and multi-team handling require signed device verification")

if __name__=="__main__":main()
