// Scarlet Crystal — first-party Apple ID login UI.
// Uses an injectable SideStore/SideSign engine interface. Never opens an
// embedded SideStore AuthenticationViewController or serializes secrets to
// launch URLs, UserDefaults, files, diagnostics, or App Groups.
import SwiftUI

@MainActor
protocol ScarletAppleSignInEngine: AnyObject {
    var isReady: Bool { get }
    func prepare() async throws
    func cancel()
    func signIn(appleID: String, password: String,
                requestTwoFactorCode: @escaping @MainActor () async throws -> String) async throws
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
    @State private var transportReady = false
    @State private var transportChecking = true
    @State private var signInTask: Task<Void, Never>?
    @State private var pendingCode: CheckedContinuation<String, Error>?

    private var readyToSubmit: Bool {
        !isAuthenticating
            && transportReady
            && !appleID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !password.isEmpty
    }

    @MainActor
    private func askForCode() async throws -> String {
        ScarletDiagnosticRecorder.shared.record("auth", "twofactor_prompt_requested")
        return try await withCheckedThrowingContinuation { continuation in
            pendingCode = continuation
            verificationCode = ""
            requiresTwoFactorCode = true
        }
    }

    private func submitCode() {
        guard verificationCode.count == 6,
              verificationCode.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }),
              let continuation = pendingCode else { return }
        pendingCode = nil
        let code = verificationCode
        verificationCode = ""
        requiresTwoFactorCode = false
        ScarletDiagnosticRecorder.shared.record("auth", "twofactor_code_submitted")
        continuation.resume(returning: code)
    }

    private func beginSignIn() {
        ScarletDiagnosticRecorder.shared.record("auth", "submit_tapped")
        guard readyToSubmit else {
            ScarletDiagnosticRecorder.shared.record("auth", "submit_incomplete",
                status: "blocked", fields: ["reason": "required_fields_missing"])
            return
        }
        // Input is always editable. Never transmit Apple credentials until
        // the SideStore/SideSign transport explicitly reports it is ready.
        guard transportReady && engine.isReady else {
            ScarletDiagnosticRecorder.shared.record("auth", "transport_unverified",
                status: "blocked", fields: ["reason": "engine_not_connected"])
            password = ""
            errorMessage = "SideStore 인증 엔진 연결이 확인되지 않았습니다."
            return
        }
        let account = appleID.trimmingCharacters(in: .whitespacesAndNewlines)
        let secret = password
        password = ""
        errorMessage = nil
        isAuthenticating = true
        ScarletDiagnosticRecorder.shared.record("auth", "request_started",
            fields: ["stage": "credentials_handoff"])
        signInTask = Task { @MainActor in
            defer {
                isAuthenticating = false
                requiresTwoFactorCode = false
            }
            do {
                try await engine.signIn(appleID: account, password: secret) {
                    try await askForCode()
                }
                ScarletDiagnosticRecorder.shared.record("auth", "request_succeeded",
                    status: "success")
                NotificationCenter.default.post(name: Notification.Name("ScarletGuestAuthVerified"), object: nil)
                dismiss()
            } catch is CancellationError {
                ScarletDiagnosticRecorder.shared.record("auth", "request_cancelled",
                    status: "cancelled")
                errorMessage = nil
            } catch {
                ScarletDiagnosticRecorder.shared.recordError("auth", "request_failed",
                    error: error)
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
                                      !verificationCode.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }))
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
                if transportChecking {
                    Section {
                        HStack {
                            ProgressView()
                            Text("SideStore 인증 엔진 연결 확인 중")
                        }
                    }
                } else if !transportReady {
                    Section {
                        Text("내장 SideStore 인증 연결 실패. 위 오류를 확인하세요.")
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
        .task {
            ScarletDiagnosticRecorder.shared.record("auth", "login_ui_opened",
                fields: ["available": engine.isReady ? "true" : "false"])
            transportChecking = true
            do {
                ScarletDiagnosticRecorder.shared.record("auth", "transport_check_started")
                try await engine.prepare()
                transportReady = engine.isReady
                if transportReady {
                    ScarletDiagnosticRecorder.shared.record("auth", "transport_ready", status: "success")
                } else {
                    ScarletDiagnosticRecorder.shared.record("auth", "transport_unverified",
                        status: "blocked", fields: ["reason": "engine_not_connected"])
                }
            } catch {
                transportReady = false
                ScarletDiagnosticRecorder.shared.record("auth", "transport_preflight_failed",
                    status: "blocked", fields: ["reason": "engine_not_connected"])
                errorMessage = error.localizedDescription
            }
            transportChecking = false
        }
        .onDisappear {
            ScarletDiagnosticRecorder.shared.record("auth", "login_ui_closed")
            signInTask?.cancel()
            engine.cancel()
            signInTask = nil
            password = ""
            verificationCode = ""
            pendingCode?.resume(throwing: CancellationError())
            pendingCode = nil
        }
        .accessibilityIdentifier("SCARLET_FIRST_PARTY_LOGIN_SHEET")
    }
}
