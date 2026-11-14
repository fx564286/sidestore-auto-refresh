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

// R6P53_STORED_AUTH_STATE_BEGIN
// A transport failure is not a negative Keychain readback. This value never
// substitutes for fresh authentication in signing/installation gates.
public enum ScarletStoredAuthState: Equatable, Sendable {
    case authenticated
    case missing
    case unavailable(reason: String)

    public static func fromWorker(_ status: Int) -> Self {
        switch status {
        case 1: return .authenticated
        case 0: return .missing
        case 2: return .unavailable(reason: "auth_worker_missing")
        default: return .unavailable(reason: "auth_reply_invalid")
        }
    }
    public var isAuthenticated: Bool { self == .authenticated }
    public var verifiedValue: Bool? {
        switch self {
        case .authenticated: return true
        case .missing: return false
        case .unavailable: return nil
        }
    }
    public var failureReason: String {
        switch self {
        case .authenticated: return "none"
        case .missing: return "auth_unavailable"
        case .unavailable: return "auth_state_unavailable"
        }
    }
}

private final class ScarletStoredAuthGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<ScarletStoredAuthState, Never>?
    init(_ continuation: CheckedContinuation<ScarletStoredAuthState, Never>) {
        self.continuation = continuation
    }
    func finish(_ value: ScarletStoredAuthState) {
        lock.lock()
        let c = continuation
        continuation = nil
        lock.unlock()
        c?.resume(returning: value)
    }
}

// Share only an in-flight read, never a cached positive/negative result.
// Login completion invalidates older reads without letting their cleanup
// remove a newer task. Late XPC/timeout callbacks are single-resume gated.
@MainActor
private final class ScarletStoredAuthReads {
    private var generation: UInt64 = 0
    private var pending: (id: UUID, task: Task<ScarletStoredAuthState, Never>)?
    func invalidate() {
        generation &+= 1
        pending = nil
    }
    func read(_ operation: @escaping @MainActor () async -> ScarletStoredAuthState)
        async -> ScarletStoredAuthState {
        let startedGeneration = generation
        let active: (id: UUID, task: Task<ScarletStoredAuthState, Never>)
        if let pending {
            active = pending
        } else {
            active = (UUID(), Task { @MainActor in await operation() })
            pending = active
        }
        let result = await active.task.value
        if pending?.id == active.id { pending = nil }
        guard startedGeneration == generation else {
            return .unavailable(reason: "auth_changed_during_read")
        }
        return result
    }
}
// R6P53_STORED_AUTH_STATE_END

@available(iOS 17.0, *)
@MainActor
public final class ScarletNativeAuthTransport {
    public static let shared = ScarletNativeAuthTransport()
    public private(set) var isReady = false
    private let storedAuthReads = ScarletStoredAuthReads()
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

    // Compatibility for existing signing/install callers remains fail closed.
    public func storedAuthenticated() async -> Bool {
        await storedAuthenticationState().isAuthenticated
    }

    public func storedAuthenticationState() async -> ScarletStoredAuthState {
        guard requestID == nil else {
            return .unavailable(reason: "auth_in_progress")
        }
        return await storedAuthReads.read { [self] in
            if !isReady {
                do { try await prepare() }
                catch { return .unavailable(reason: "auth_transport_unavailable") }
            }
            guard let remote = RefreshHandler.shared.client else {
                isReady = false
                return .unavailable(reason: "auth_transport_unavailable")
            }
            let state = await withCheckedContinuation {
                (c: CheckedContinuation<ScarletStoredAuthState, Never>) in
                let gate = ScarletStoredAuthGate(c)
                DispatchQueue.main.asyncAfter(deadline: .now() + 12) {
                    gate.finish(.unavailable(reason: "auth_state_read_timeout"))
                }
                remote.scarletAuthStoredState { status in
                    gate.finish(.fromWorker(status))
                }
            }
            if case .unavailable = state { isReady = false }
            return state
        }
    }

    public func signIn(email: String, password: String,
                       anisetteProfile: String,
                       codeProvider: @escaping () async throws -> String) async throws {
        guard requestID == nil else { throw ScarletNativeAuthError.alreadyRunning }
        storedAuthReads.invalidate()
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
        storedAuthReads.invalidate()
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

@available(iOS 17.0, *)
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
                let status = rawStatus ?? "worker_unknown"
                gate.finish(ScarletNativeRefreshInspection(
                    count: max(0, min(Int(count), 99)),
                    hostManaged: managed, signingReady: cert,
                    reason: allowed.contains(status) ? status : "worker_unknown"))
            }
        }
    }
}

// Original SideStore AppManager performs signing + installation inside the
// embedded LiveProcess, not inside the LiveContainer host's AppIntent proxy.
// Never turn a returning operation into an unverified installation success.
// R6P34_NATIVE_EVIDENCE_BEGIN
public struct ScarletNativeRefreshEvidence: Codable, Sendable {
    public let v: Int
    public let reason: String
    public let stage: String
    public let domain: String
    public let code: Int
    public let kind: String
    public let underlyingDomain: String
    public let underlyingCode: Int
    public let underlyingKind: String
    public let depth: Int

    public static func decode(_ wire: String) -> ScarletNativeRefreshEvidence? {
        let prefix = "scarlet_native_failure:"
        guard wire.hasPrefix(prefix), wire.utf8.count <= 1024,
              let data = String(wire.dropFirst(prefix.count)).data(using: .utf8),
              let value = try? JSONDecoder().decode(Self.self, from: data) else { return nil }
        let domains: Set<String> = ["operation", "url", "cocoa", "posix", "osstatus",
            "altserver", "altsign", "appleapi", "other", "none"]
        let kinds: Set<String> = ["unknown_result", "invalid_app", "invalid_response",
            "missing_app_bundle", "missing_info_plist", "missing_update", "forbidden",
            "pledge_inactive", "no_sources", "cache_clear", "open_app_failed",
            "sidejit", "classified_operation", "other", "none"]
        guard value.v == 1, value.reason.utf8.count <= 80,
              ["database", "team", "transport", "refresh"].contains(value.stage),
              domains.contains(value.domain), domains.contains(value.underlyingDomain),
              kinds.contains(value.kind), kinds.contains(value.underlyingKind),
              (-2_147_483_648...2_147_483_647).contains(value.code),
              (-2_147_483_648...2_147_483_647).contains(value.underlyingCode),
              (0...4).contains(value.depth) else { return nil }
        return value
    }

    public var diagnosticFields: [String: String] {
        ["native_error_stage": stage, "native_error_domain": domain,
         "native_error_code": String(code), "native_error_kind": kind,
         "native_underlying_domain": underlyingDomain,
         "native_underlying_code": String(underlyingCode),
         "native_underlying_kind": underlyingKind, "native_error_depth": String(depth)]
    }
}
// R6P34_NATIVE_EVIDENCE_END

@available(iOS 17.0, *)
public struct ScarletNativeRefreshFailure: Error, Sendable, CustomNSError {
    public let reason: String
    public let nativeEvidence: ScarletNativeRefreshEvidence?
    public init(reason: String, nativeEvidence: ScarletNativeRefreshEvidence? = nil) {
        self.reason = reason
        self.nativeEvidence = nativeEvidence
    }
    public static var errorDomain: String { "SideStoreSupport.ScarletNativeRefreshFailure" }
    public var errorCode: Int { 1 }
    public var errorUserInfo: [String: Any] {
        guard let evidence = nativeEvidence else { return [:] }
        return ["ScarletNativeRefreshEvidence": evidence.diagnosticFields]
    }
}

@available(iOS 17.0, *)
private final class ScarletRefreshExecutionGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<(Bool, String), Never>?
    init(_ continuation: CheckedContinuation<(Bool, String), Never>) {
        self.continuation = continuation
    }
    func finish(_ completed: Bool, _ reason: String) {
        lock.lock()
        let c = continuation
        continuation = nil
        lock.unlock()
        c?.resume(returning: (completed, reason))
    }
}

@available(iOS 17.0, *)
@MainActor
public enum ScarletNativeRefreshExecutor {
    public static func execute() async throws -> String {
        do {
            try await ScarletNativeAuthTransport.shared.prepare()
        } catch {
            throw ScarletNativeRefreshFailure(reason: "transport_unavailable")
        }
        guard let client = RefreshHandler.shared.client else {
            throw ScarletNativeRefreshFailure(reason: "transport_unavailable")
        }
        let (returned, rawReason) = await withCheckedContinuation {
            (c: CheckedContinuation<(Bool, String), Never>) in
            let gate = ScarletRefreshExecutionGate(c)
            // A dead LiveProcess should be classified, not shown forever
            // as a running renewal. This watchdog is not the refresh
            // implementation; actual work runs in SideStore AppManager.
            DispatchQueue.main.asyncAfter(deadline: .now() + 600) {
                gate.finish(false, "worker_unresponsive")
            }
            client.scarletPerformNativeRefresh { completed, reason in
                gate.finish(completed, reason ?? "sidestore_native_operation_failed")
            }
        }
        let allowed: Set<String> = [
            "native_operation_returned_unverified",
            "native_operation_returned_unverified_transport_recovered",
            "native_profile_date_advanced_install_unverified",
            "native_refresh_record_updated_install_unverified",
            "already_running",
            "anisette_unavailable", "vpn_unavailable", "signing_failed",
            "profile_refresh_failed", "server_unavailable",
            "installation_failed", "sidestore_native_operation_failed",
            "sidestore_database_unavailable", "no_managed_apps",
            "host_not_managed", "host_not_in_refresh_results",
            "sidestore_certificate_missing", "refresh_worker_missing", "transport_unavailable",
            "worker_unresponsive", "pairing_file_missing", "pairing_invalid",
            "minimuxer_not_started", "device_network_unavailable",
            "device_endpoint_unavailable", "sidestore_auth_missing",
            "device_identifier_unavailable", "certificate_expired",
            "certificate_revoked", "profile_missing", "app_group_missing",
            "device_operation_timed_out", "sidestore_invalid_configuration",
            "sidestore_team_mismatch", "sidestore_team_recovery_failed",
            "native_worker_creation_failed",
            // R6P24: R6P23's four static native stage receipts must survive
            // this independent host XPC allowlist. Do not pass raw errors.
            "native_unknown_database_stage", "native_unknown_team_stage",
            "native_unknown_transport_stage", "native_unknown_appmanager_stage"
        ]
        let nativeEvidence = returned ? nil : ScarletNativeRefreshEvidence.decode(rawReason)
        let candidateReason = nativeEvidence?.reason ?? rawReason
        let status = allowed.contains(candidateReason)
            ? candidateReason : "sidestore_native_operation_failed"
        guard returned && (
            status == "native_operation_returned_unverified" ||
            status == "native_operation_returned_unverified_transport_recovered" ||
            status == "native_profile_date_advanced_install_unverified" ||
            status == "native_refresh_record_updated_install_unverified"
        ) else {
            throw ScarletNativeRefreshFailure(reason: status,
                nativeEvidence: allowed.contains(candidateReason) ? nativeEvidence : nil)
        }
        return status
    }
}

// V29: safely install a newly generated iOS-27 RPPairing record into the
// original embedded SideStore only AFTER it passed live Minimuxer validation.
// This path handles pairing data entirely on this iPhone, never uploads it.
@available(iOS 17.0, *)
private final class ScarletPairingCommitGate: @unchecked Sendable {
    private let lock = NSLock()
    private var pending: CheckedContinuation<(Bool, String), Never>?
    init(_ continuation: CheckedContinuation<(Bool, String), Never>) {
        pending = continuation
    }
    func finish(_ accepted: Bool, reason: String) {
        lock.lock()
        let c = pending
        pending = nil
        lock.unlock()
        c?.resume(returning: (accepted, reason))
    }
}

@available(iOS 17.0, *)
@MainActor
public enum ScarletNativePairingInstaller {
    public static func inspectPersistedState() async -> (Bool, String) {
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return (false, "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else {
            return (false, "transport_unavailable")
        }
        let (verified, rawStatus) = await withCheckedContinuation {
            (c: CheckedContinuation<(Bool, String), Never>) in
            let gate = ScarletPairingCommitGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 20) {
                gate.finish(false, reason: "pairing_state_read_timeout")
            }
            client.scarletInspectDevicePairing { ready, status in
                gate.finish(ready, reason: status ?? "pairing_state_read_failed")
            }
        }
        let allowed: Set<String> = [
            "pairing_saved_and_transport_ready", "pairing_file_missing",
            "pairing_invalid", "pairing_protocol_mismatch",
            "pairing_saved_transport_unavailable", "transport_unavailable",
            "refresh_worker_missing", "pairing_state_read_timeout",
            "pairing_state_read_failed"
        ]
        let reason = allowed.contains(rawStatus)
            ? rawStatus : "pairing_state_read_failed"
        return (verified && reason == "pairing_saved_and_transport_ready", reason)
    }

    public static func install(candidate: Data) async -> (Bool, String) {
        guard candidate.count > 128 && candidate.count <= 1024 * 1024 else {
            return (false, "pairing_file_invalid")
        }
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return (false, "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else {
            return (false, "transport_unavailable")
        }
        let (accepted, originalReason) = await withCheckedContinuation {
            (c: CheckedContinuation<(Bool, String), Never>) in
            let gate = ScarletPairingCommitGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 90) {
                gate.finish(false, reason: "pairing_validation_unresponsive")
            }
            client.scarletInstallPairingRecord(candidate) { ok, reason in
                gate.finish(ok, reason: reason ?? "pairing_validation_failed")
            }
        }
        let allowed: Set<String> = [
            "pairing_saved_and_transport_ready", "pairing_file_invalid",
            "pairing_protocol_mismatch", "pairing_file_missing",
            "pairing_invalid", "minimuxer_not_started",
            "vpn_unavailable", "device_endpoint_unavailable",
            "device_network_unavailable", "transport_unavailable",
            "pairing_validation_unresponsive", "pairing_validation_failed",
            "refresh_worker_missing", "sidestore_native_operation_failed"
        ]
        let reason = allowed.contains(originalReason) ? originalReason
            : "pairing_validation_failed"
        return (accepted && reason == "pairing_saved_and_transport_ready", reason)
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


// R6P61_SLOT_MANAGER_BEGIN
public struct ScarletSideloadSlot: Identifiable, Decodable, Sendable {
    public let id: String
    public let name: String
    public let active: Bool
    public let editable: Bool
}

@available(iOS 17.0, *)
@MainActor
public enum ScarletNativeSideloadSlots {
    public static func list() async -> (apps: [ScarletSideloadSlot], reason: String) {
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return ([], "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else { return ([], "transport_unavailable") }
        return await withCheckedContinuation { c in
            let gate = ScarletSlotsListGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 20) {
                gate.finish([], "timeout")
            }
            client.scarletManagedSlots { json, reason in
                let raw = json ?? "[]"
                guard raw.utf8.count <= 64000,
                      let bytes = raw.data(using: .utf8),
                      let rows = try? JSONDecoder().decode([ScarletSideloadSlot].self, from: bytes),
                      rows.count <= 80,
                      rows.allSatisfy({ $0.id.utf8.count <= 200 && $0.name.utf8.count <= 120 }) else {
                    gate.finish([], "response_invalid"); return
                }
                let status = reason ?? "worker_unknown"
                gate.finish(rows, ["ready", "database_unavailable", "response_too_large",
                                   "slot_worker_missing"].contains(status) ? status : "worker_unknown")
            }
        }
    }
    public static func change(bundleID: String, active: Bool) async -> (Bool, String) {
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return (false, "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else { return (false, "transport_unavailable") }
        return await withCheckedContinuation { c in
            let gate = ScarletSlotChangeGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 240) {
                gate.finish(false, "timeout_device_state_unknown")
            }
            client.scarletSetManagedSlot(bundleID, active: active) { ok, reason in
                let status = reason ?? "worker_unknown"
                let allowed = ["side_store_pipeline_returned_device_unverified",
                    "already_in_requested_state", "coredata_state_unverified",
                    "active_slot_full", "app_not_managed", "invalid_request", "host_protected",
                    "operation_in_progress", "activation_or_restore_failed",
                    "backup_or_deactivation_failed", "database_unavailable", "slot_worker_missing"]
                gate.finish(ok, allowed.contains(status) ? status : "worker_unknown")
            }
        }
    }
}

private final class ScarletSlotsListGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<(apps: [ScarletSideloadSlot], reason: String), Never>?
    init(_ c: CheckedContinuation<(apps: [ScarletSideloadSlot], reason: String), Never>) { continuation = c }
    func finish(_ apps: [ScarletSideloadSlot], _ reason: String) {
        lock.lock(); let c = continuation; continuation = nil; lock.unlock()
        c?.resume(returning: (apps, reason))
    }
}
private final class ScarletSlotChangeGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<(Bool, String), Never>?
    init(_ c: CheckedContinuation<(Bool, String), Never>) { continuation = c }
    func finish(_ ok: Bool, _ reason: String) {
        lock.lock(); let c = continuation; continuation = nil; lock.unlock()
        c?.resume(returning: (ok, reason))
    }
}
// R6P61_SLOT_MANAGER_END
