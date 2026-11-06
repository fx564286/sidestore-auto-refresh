// Scarlet Crystal — first-party Apple ID login UI.
// Uses an injectable SideStore/SideSign engine interface. Never opens an
// embedded SideStore AuthenticationViewController or serializes secrets to
// launch URLs, UserDefaults, files, diagnostics, or App Groups.
import SwiftUI

@MainActor
protocol ScarletAppleSignInEngine: AnyObject {
    var isReady: Bool { get }
    func signIn(appleID: String, password: String,
                requestTwoFactorCode: @escaping @MainActor () async throws -> String) async throws
}

enum ScarletSignInBridgeError: LocalizedError {
    case engineNotConnected
    var errorDescription: String? {
        switch self {
        case .engineNotConnected:
            return "SideStore 인증 엔진의 안전한 연결이 아직 검증되지 않았습니다."
        }
    }
}

// The current SideStore binary is isolated as a LiveContainer guest.
// Calling its guest UI is NOT an acceptable replacement for an in-host
// authentication transport. Fail closed until a real, validated secure
// engine bridge is implemented and device-tested.
@MainActor
final class ScarletPendingSideStoreEngineBridge: ScarletAppleSignInEngine {
    var isReady: Bool { false }
    func signIn(appleID: String, password: String,
                requestTwoFactorCode: @escaping @MainActor () async throws -> String) async throws {
        throw ScarletSignInBridgeError.engineNotConnected
    }
}

@available(iOS 17.0, *)
struct ScarletAppleIDLoginSheet: View {
    let engine: any ScarletAppleSignInEngine
    @Environment(\.dismiss) private var dismiss

    @State private var appleID = ""
    @State private var password = ""
    @State private var verificationCode = ""
    @State private var isAuthenticating = false
    @State private var requiresTwoFactorCode = false
    @State private var errorMessage: String?
    @State private var success = false
    @State private var pendingCode: CheckedContinuation<String, Error>?

    private var readyToSubmit: Bool {
        engine.isReady && !isAuthenticating
            && !appleID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !password.isEmpty
    }

    @MainActor
    private func askForCode() async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            pendingCode = continuation
            verificationCode = ""
            requiresTwoFactorCode = true
        }
    }

    private func submitCode() {
        guard verificationCode.count == 6,
              verificationCode.allSatisfy(\.isNumber),
              let continuation = pendingCode else { return }
        pendingCode = nil
        let code = verificationCode
        verificationCode = ""
        requiresTwoFactorCode = false
        continuation.resume(returning: code)
    }

    private func beginSignIn() {
        guard readyToSubmit else { return }
        let account = appleID.trimmingCharacters(in: .whitespacesAndNewlines)
        let secret = password
        password = ""
        errorMessage = nil
        isAuthenticating = true
        Task { @MainActor in
            defer {
                isAuthenticating = false
                requiresTwoFactorCode = false
            }
            do {
                try await engine.signIn(appleID: account, password: secret) {
                    try await askForCode()
                }
                success = true
                dismiss()
            } catch is CancellationError {
                errorMessage = nil
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                if requiresTwoFactorCode {
                    Section("Apple 2단계 인증") {
                        TextField("6자리 인증번호", text: $verificationCode)
                            .keyboardType(.numberPad)
                            .textContentType(.oneTimeCode)
                            .accessibilityIdentifier("SCARLET_2FA_CODE")
                        Button("인증번호 확인", action: submitCode)
                            .disabled(verificationCode.count != 6 ||
                                      !verificationCode.allSatisfy(\.isNumber))
                    }
                } else {
                    Section("Apple ID") {
                        TextField("이메일", text: $appleID)
                            .keyboardType(.emailAddress)
                            .textContentType(.username)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .accessibilityIdentifier("SCARLET_APPLE_ID_FIELD")
                        SecureField("비밀번호", text: $password)
                            .textContentType(.password)
                            .accessibilityIdentifier("SCARLET_APPLE_PASSWORD_FIELD")
                    }
                    Section {
                        Button("로그인", action: beginSignIn)
                            .frame(maxWidth: .infinity)
                            .disabled(!readyToSubmit)
                            .accessibilityIdentifier("SCARLET_OWN_LOGIN_SUBMIT")
                    }
                }
                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                            .accessibilityIdentifier("SCARLET_LOGIN_ERROR")
                    }
                }
                if !engine.isReady {
                    Section {
                        Text("인증 엔진 연결 미검증 · 로그인 비활성화")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Apple ID 로그인")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("닫기") { dismiss() }
                }
            }
        }
        .onDisappear {
            password = ""
            verificationCode = ""
            pendingCode?.resume(throwing: CancellationError())
            pendingCode = nil
        }
        .accessibilityIdentifier("SCARLET_FIRST_PARTY_LOGIN_SHEET")
    }
}
