// Scarlet Crystal authenticated engine transport — experimental.
// Only SideStore's existing headless SignInOperation may perform Apple login.
// This framework keeps secret values in process/XPC memory; never URL/files.
import Foundation
import Combine

public enum ScarletHostAuthError: LocalizedError {
    case busy, noSideStore, noLiveProcess, noPrivateChannel, cancelled
    case backend(String)

    public var errorDescription: String? {
        switch self {
        case .busy: return "다른 서명 또는 로그인 작업이 실행 중입니다."
        case .noSideStore: return "내장 SideStore 인증 엔진을 찾지 못했습니다."
        case .noLiveProcess: return "LiveProcess 확장이 설치되지 않았습니다."
        case .noPrivateChannel: return "SideStore 백그라운드 인증 채널에 연결할 수 없습니다."
        case .cancelled: return "인증 요청이 취소됐습니다."
        case .backend(let message): return message
        }
    }
}

@available(iOS 17.0, *)
@MainActor
public final class ScarletSideStoreAuthTransport: ObservableObject {
    public static let shared = ScarletSideStoreAuthTransport()
    @Published public private(set) var isAuthenticated = false
    @Published public private(set) var operationInProgress = false

    private var codeProvider: ((String) async throws -> String)?
    private init() {}

    public var isEnginePresent: Bool { UserDefaults.sideStoreExist() }

    public func signIn(appleID: String,
                       password: String,
                       requestCode: @escaping (String) async throws -> String) async throws {
        guard isEnginePresent else { throw ScarletHostAuthError.noSideStore }
        guard !operationInProgress else { throw ScarletHostAuthError.busy }
        operationInProgress = true
        codeProvider = requestCode
        defer {
            codeProvider = nil
            operationInProgress = false
        }
        try await RefreshHandler.shared.scarletEnsureBackgroundEngine()
        guard let client = RefreshHandler.shared.client else {
            throw ScarletHostAuthError.noPrivateChannel
        }
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            client.scarletAuthenticate(withAppleID: appleID, password: password) { error in
                if let error, !error.isEmpty {
                    continuation.resume(throwing: ScarletHostAuthError.backend(error))
                } else {
                    continuation.resume()
                }
            }
        }
        isAuthenticated = true
    }

    fileprivate func requestTwoFactor(prompt: String,
                                      reply: @escaping (String?) -> Void) {
        guard let codeProvider else { reply(nil); return }
        Task { @MainActor in
            do {
                let code = try await codeProvider(prompt)
                guard code.utf8.count == 6,
                      code.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }) else {
                    reply(nil)
                    return
                }
                reply(code)
            } catch {
                reply(nil)
            }
        }
    }
}

@available(iOS 17.0, *)
extension RefreshHandler {
    // Required by extended original RefreshServer XPC protocol.
    @objc(scarletRequest2FACodeForPrompt:reply:)
    func scarletRequest2FACode(_ prompt: String,
                               reply: @escaping (String?) -> Void) {
        Task { @MainActor in
            ScarletSideStoreAuthTransport.shared.requestTwoFactor(
                prompt: prompt, reply: reply)
        }
    }

    // Extends the original SideStore refresh transport without changing its
    // refresh operation. Refuses concurrent in-flight refresh tasks.
    @MainActor
    func scarletEnsureBackgroundEngine() async throws {
        if c != nil || launchContinuation != nil {
            throw ScarletHostAuthError.busy
        }
        if listener == nil {
            guard let existing = startAnonymousListener(self) else {
                throw ScarletHostAuthError.noPrivateChannel
            }
            listener = existing
        }
        guard let endpoint = listener?.endpoint else {
            throw ScarletHostAuthError.noPrivateChannel
        }
        if sideStorePid <= 0 || getpgid(sideStorePid) <= 0 {
            guard let rawHome = getenv("LC_HOME_PATH") else {
                throw ScarletHostAuthError.noSideStore
            }
            let home = URL(fileURLWithPath: String(cString: rawHome))
                .appendingPathComponent("Documents/SideStore", isDirectory: true)
            guard let bookmark = bookmarkForURL(home) else {
                throw ScarletHostAuthError.noSideStore
            }
            guard let extensionURL = UserDefaults.lcMainBundle().builtInPlugInsURL?
                .appendingPathComponent("LiveProcess.appex"),
                  let bundle = Bundle(url: extensionURL),
                  let identifier = bundle.bundleIdentifier else {
                throw ScarletHostAuthError.noLiveProcess
            }
            let ext = try NSExtension(identifier: identifier)
            let item = NSExtensionItem()
            item.userInfo = [
                "selected": "builtinSideStore",
                "bookmarks": [bookmark],
                "endpoint": endpoint
            ]
            self.ext = ext
            ext.setRequestInterruptionBlock { _ in
                self.sideStorePid = 0
                if let c = self.launchContinuation {
                    self.launchContinuation = nil
                    c.resume(throwing: ScarletHostAuthError.noPrivateChannel)
                }
            }
            let uuid = await ext.beginRequest(withInputItems: [item])
            sideStorePid = ext.pid(forRequestIdentifier: uuid)
            try await withUnsafeThrowingContinuation { (continuation: UnsafeContinuation<Void, Error>) in
                launchContinuation = continuation
                DispatchQueue.main.asyncAfter(deadline: .now() + 35) {
                    if let c = self.launchContinuation {
                        self.launchContinuation = nil
                        c.resume(throwing: ScarletHostAuthError.noPrivateChannel)
                    }
                }
            }
        }
        guard client != nil else {
            throw ScarletHostAuthError.noPrivateChannel
        }
    }
}
