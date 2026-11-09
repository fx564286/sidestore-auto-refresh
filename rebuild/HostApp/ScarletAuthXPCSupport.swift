// Scarlet guest SideSign transport. Compiled in pinned SideStoreSupport target.
// Uses only the existing anonymous LiveProcess XPC channel.
import Foundation
import AppIntents

@available(iOS 17.0, *)
public enum ScarletNativeAuthError: LocalizedError {
    case guestUnavailable
    case workerUnavailable
    case alreadyRunning
    case timedOut
    case remoteFailure(domain: String, code: Int)

    public var errorDescription: String? {
        switch self {
        case .guestUnavailable: return "내장 SideStore LiveProcess 인증 연결에 실패했습니다."
        case .workerUnavailable: return "SideStore 인증 처리기가 연결되지 않았습니다."
        case .alreadyRunning: return "다른 Apple 인증 작업이 진행 중입니다."
        case .timedOut: return "SideStore 인증 통신 시간이 초과되었습니다."
        case .remoteFailure(let domain, let code):
            return "Apple 인증 실패: " + domain + " (" + String(code) + ")"
        }
    }
}

private final class ScarletBoolGate: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false
    private var continuation: CheckedContinuation<Bool, Never>?
    init(_ continuation: CheckedContinuation<Bool, Never>) { self.continuation = continuation }
    func finish(_ value: Bool) {
        lock.lock()
        guard !done else { lock.unlock(); return }
        done = true
        let c = continuation
        continuation = nil
        lock.unlock()
        c?.resume(returning: value)
    }
}

@available(iOS 17.0, *)
@MainActor
public final class ScarletNativeAuthTransport {
    public static let shared = ScarletNativeAuthTransport()
    public private(set) var isReady = false
    private var requestID: String?
    private var completion: CheckedContinuation<Void, Error>?
    private var codeProvider: (() async throws -> String)?
    private init() {}

    public func prepare() async throws {
        isReady = false
        try await RefreshHandler.shared.scarletEnsureAuthGuest()
        guard let remote = RefreshHandler.shared.client else {
            throw ScarletNativeAuthError.guestUnavailable
        }
        let verified = await withCheckedContinuation { (c: CheckedContinuation<Bool, Never>) in
            let gate = ScarletBoolGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 15) { gate.finish(false) }
            remote.scarletAuthReady { ready in gate.finish(ready) }
        }
        guard verified else { throw ScarletNativeAuthError.workerUnavailable }
        isReady = true
    }

    // Ask the real SideStore worker to re-read its Keychain every time a
    // host scene starts or an auth sheet is reopened. Do not cache a false
    // "logged in" badge from a one-time XPC success notification.
    public func storedAuthenticated() async -> Bool {
        if !isReady {
            do { try await prepare() }
            catch { return false }
        }
        guard let remote = RefreshHandler.shared.client else { return false }
        return await withCheckedContinuation { (c: CheckedContinuation<Bool, Never>) in
            let gate = ScarletBoolGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 12) {
                gate.finish(false)
            }
            remote.scarletAuthStored { stored in
                gate.finish(stored)
            }
        }
    }

    public func signIn(email: String, password: String,
                       anisetteProfile: String,
                       codeProvider: @escaping () async throws -> String) async throws {
        guard requestID == nil else { throw ScarletNativeAuthError.alreadyRunning }
        try await prepare()
        guard let remote = RefreshHandler.shared.client else {
            throw ScarletNativeAuthError.guestUnavailable
        }
        let id = UUID().uuidString
        requestID = id
        self.codeProvider = codeProvider
        defer {
            requestID = nil
            self.codeProvider = nil
            completion = nil
        }
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            completion = c
            remote.scarletBeginAuth(id, email: email, password: password,
                                    profile: anisetteProfile)
            Task { @MainActor in
                try? await Task.sleep(for: .seconds(360))
                if self.requestID == id {
                    remote.scarletCancelAuth(id)
                    self.finish(id, error: ScarletNativeAuthError.timedOut)
                }
            }
        }
    }

    public func cancel() {
        guard let id = requestID else { return }
        RefreshHandler.shared.client?.scarletCancelAuth(id)
        finish(id, error: CancellationError())
    }

    func needsCode(_ id: String) {
        guard requestID == id, let provider = codeProvider else { return }
        Task { @MainActor in
            do {
                let code = try await provider()
                guard self.requestID == id else { return }
                guard code.count == 6, code.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }) else {
                    throw ScarletNativeAuthError.remoteFailure(domain: "twofactor.invalid_input", code: -1)
                }
                RefreshHandler.shared.client?.scarletProvideCode(id, code: code)
            } catch {
                RefreshHandler.shared.client?.scarletCancelAuth(id)
                self.finish(id, error: error)
            }
        }
    }

    func finished(_ id: String, code: Int, domain: String) {
        finish(id, error: code == 0 ? nil :
                ScarletNativeAuthError.remoteFailure(domain: domain, code: code))
    }

    private func finish(_ id: String, error: Error?) {
        guard requestID == id, let c = completion else { return }
        completion = nil
        if let error { c.resume(throwing: error) } else { c.resume() }
    }
}

extension RefreshHandler {
    // ObjC protocol requirements must be implemented at the target's
    // minimum deployment version even though auth starts only on iOS 17+.
    @objc func scarletAuthNeedsCode(_ requestID: String) {
        if #available(iOS 17.0, *) {
            Task { @MainActor in ScarletNativeAuthTransport.shared.needsCode(requestID) }
        }
    }

    @objc func scarletAuthCompleted(_ requestID: String, code: Int, domain: String) {
        if #available(iOS 17.0, *) {
            Task { @MainActor in
                ScarletNativeAuthTransport.shared.finished(requestID, code: code, domain: domain)
            }
        }
    }
}

// Real worker inspection, not an assumption based on Apple login or host
// provisioning. SideStore refreshes its OWN database of managed InstalledApp.
@available(iOS 17.0, *)
public struct ScarletNativeRefreshInspection: Sendable {
    public let count: Int
    public let hostManaged: Bool
    public let signingReady: Bool
    public let reason: String

    public init(count: Int, hostManaged: Bool, signingReady: Bool, reason: String) {
        self.count = count
        self.hostManaged = hostManaged
        self.signingReady = signingReady
        self.reason = reason
    }
    public var canRefreshHost: Bool {
        hostManaged && signingReady && reason == "ready"
    }
}

private final class ScarletRefreshInspectionGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<ScarletNativeRefreshInspection, Never>?
    init(_ c: CheckedContinuation<ScarletNativeRefreshInspection, Never>) {
        continuation = c
    }
    func finish(_ result: ScarletNativeRefreshInspection) {
        lock.lock()
        let c = continuation
        continuation = nil
        lock.unlock()
        c?.resume(returning: result)
    }
}

@available(iOS 17.0, *)
@MainActor
public enum ScarletNativeRefreshInspector {
    public static func inspect() async -> ScarletNativeRefreshInspection {
        // Reuse the SAME embedded LiveProcess guest and XPC used by SignIn,
        // but query the SideStore DB instead of treating login as readiness.
        do {
            try await ScarletNativeAuthTransport.shared.prepare()
        } catch {
            return ScarletNativeRefreshInspection(count: 0, hostManaged: false,
                signingReady: false, reason: "transport_unavailable")
        }
        guard let client = RefreshHandler.shared.client else {
            return ScarletNativeRefreshInspection(count: 0, hostManaged: false,
                signingReady: false, reason: "transport_unavailable")
        }
        return await withCheckedContinuation { c in
            let gate = ScarletRefreshInspectionGate(c)
            // A dead XPC connection must return a diagnostic status instead
            // of leaving the user's UI permanently at '요청 중'.
            DispatchQueue.main.asyncAfter(deadline: .now() + 20) {
                gate.finish(ScarletNativeRefreshInspection(count: 0,
                    hostManaged: false, signingReady: false,
                    reason: "transport_unresponsive"))
            }
            client.scarletRefreshReadiness { count, managed, cert, rawStatus in
                // Allowlist classifications; never transfer DB, Apple ID,
                // P12 or user-supplied error strings.
                let allowed = [
                    "ready", "no_managed_apps", "host_not_managed",
                    "sidestore_certificate_missing", "sidestore_database_unavailable",
                    "refresh_worker_missing"
                ]
                let status = String(rawStatus)
                gate.finish(ScarletNativeRefreshInspection(
                    count: max(0, min(Int(count), 99)),
                    hostManaged: managed, signingReady: cert,
                    reason: allowed.contains(status) ? status : "worker_unknown"))
            }
        }
    }
}

@available(iOS 17.0, *)
extension RefreshHandler {
    func scarletEnsureAuthGuest() async throws {
        if client != nil { return }
        if listener == nil {
            guard let activeListener = startAnonymousListener(self) else {
                throw ScarletNativeAuthError.guestUnavailable
            }
            listener = activeListener
        }
        if sideStorePid <= 0 || getpgid(sideStorePid) <= 0 {
            guard let pointer = getenv("LC_HOME_PATH") else {
                throw ScarletNativeAuthError.guestUnavailable
            }
            let home = URL(fileURLWithPath: String(cString: pointer))
            let guestHome = home.appendingPathComponent("Documents/SideStore")
            guard let bookmark = bookmarkForURL(guestHome),
                  let endpoint = listener?.endpoint,
                  let extensionURL = UserDefaults.lcMainBundle().builtInPlugInsURL?
                    .appendingPathComponent("LiveProcess.appex"),
                  let extensionBundle = Bundle(url: extensionURL) else {
                throw ScarletNativeAuthError.guestUnavailable
            }
            let request = NSExtensionItem()
            request.userInfo = ["selected": "builtinSideStore",
                                "bookmarks": [bookmark],
                                "endpoint": endpoint]
            let process = try NSExtension(identifier: extensionBundle.bundleIdentifier)
            ext = process
            process.setRequestInterruptionBlock { _ in
                Task { @MainActor in ScarletNativeAuthTransport.shared.cancel() }
            }
            let identifier = await process.beginRequest(withInputItems: [request])
            sideStorePid = process.pid(forRequestIdentifier: identifier)
        }
        for _ in 0..<80 {
            if client != nil { return }
            try await Task.sleep(for: .milliseconds(250))
        }
        throw ScarletNativeAuthError.guestUnavailable
    }
}
