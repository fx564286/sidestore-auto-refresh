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
            switch domain {
            case "scarlet.auth.keychain_roundtrip_failed":
                return "새 Apple ID 인증 정보 확인에 실패했습니다. 이전 계정 복원 결과를 확인하세요. (" + String(code) + ")"
            case "scarlet.auth.keychain_write_failed":
                return "계정별 보안 저장이 실패했습니다. 기존 계정 인증 정보는 삭제하지 않았습니다. (" + String(code) + ")"
            case "scarlet.auth.rollback_unverified":
                return "이전 계정 복원 결과를 확인하지 못했습니다. 추가 로그인이나 서명 작업을 진행하기 전에 저장된 계정을 다시 확인하세요. (" + String(code) + ")"
            default:
                return "Apple 인증 실패: " + domain + " (" + String(code) + ")"
            }
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
    // One LIVE worker handshake at a time. Concurrent account/refresh calls
    // must not tear each other's native XPC session down.
    private var preparingWorker: Task<Void, Error>?
    private init() {}

    public func prepare() async throws {
        if let preparingWorker {
            try await preparingWorker.value
            return
        }
        let operation = Task { @MainActor in
            try await self.prepareConnectedWorker()
        }
        preparingWorker = operation
        defer { preparingWorker = nil }
        try await operation.value
    }

    private func workerResponds(_ remote: RefreshClient) async -> Bool {
        await withCheckedContinuation { (c: CheckedContinuation<Bool, Never>) in
            let gate = ScarletBoolGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 15) {
                gate.finish(false)
            }
            remote.scarletAuthReady { ready in gate.finish(ready) }
        }
    }

    private func prepareConnectedWorker() async throws {
        isReady = false
        try await RefreshHandler.shared.scarletEnsureAuthGuest()
        guard let remote = RefreshHandler.shared.client else {
            throw ScarletNativeAuthError.guestUnavailable
        }
        if await workerResponds(remote) {
            isReady = true
            return
        }
        // A cached NSXPC proxy is not evidence of a live SideStore worker.
        // Retire only that exact failed proxy, only when native refresh and
        // extension startup are idle. Preserve the selected Apple ID/P12.
        guard RefreshHandler.shared.scarletRetireFailedAuthGuest(expected: remote) else {
            throw ScarletNativeAuthError.workerUnavailable
        }
        try await RefreshHandler.shared.scarletEnsureAuthGuest()
        guard let recovered = RefreshHandler.shared.client,
              await workerResponds(recovered) else {
            throw ScarletNativeAuthError.workerUnavailable
        }
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

    public func scarletAccountWasSwitched() {
        storedAuthReads.invalidate()
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
    public var canRefreshSelectedTeam: Bool {
        signingReady && (reason == "ready" || reason == "ready_selected_team")
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
            client.scarletRefreshReadiness(Bundle.main.bundleURL.path) { count, managed, cert, rawStatus in
                // Allowlist classifications; never transfer DB, Apple ID,
                // P12 or user-supplied error strings.
                let allowed = [
                    "ready", "ready_selected_team", "no_managed_apps",
                    "no_managed_apps_for_selected_team",
                    "managed_apps_inactive_for_selected_team",
                    "managed_apps_excluded_from_refresh_for_selected_team",
                    "selected_team_inventory_unavailable", "host_not_managed",
                    "host_registration_failed", "host_bundle_path_unavailable",
                    "host_signed_bundle_unavailable", "host_identity_mismatch",
                    "host_selected_team_mismatch",
                    "host_selected_team_certificate_missing",
                    "host_payload_cache_unavailable", "host_cached_bundle_mismatch",
                    "host_team_record_missing",
                    "host_managed_owner_mismatch", "host_managed_record_inactive",
                    "sidestore_certificate_missing", "selected_team_certificate_missing",
                    "sidestore_database_unavailable",
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
    public static func execute(manual: Bool = false,
                               certificateRotation: Bool = false,
                               selectedAccountID: String? = nil,
                               selectedTeamID: String? = nil) async throws -> String {
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
            let finished: (Bool, String?) -> Void = { completed, reason in
                gate.finish(completed, reason ?? "sidestore_native_operation_failed")
            }
            if certificateRotation {
                // The host selection is an immutable input for this native
                // transaction, not a worker-time read of global active state.
                guard let selectedAccountID, !selectedAccountID.isEmpty,
                      let selectedTeamID, !selectedTeamID.isEmpty else {
                    gate.finish(false, "selected_account_owner_unverified")
                    return
                }
                client.scarletPerformSelectedHostResign(
                    Bundle.main.bundleURL.path,
                    accountID: selectedAccountID, teamID: selectedTeamID,
                    reply: finished)
            } else if manual {
                client.scarletPerformManualNativeRefresh(
                    Bundle.main.bundleURL.path, reply: finished)
            } else {
                client.scarletPerformNativeRefresh(
                    Bundle.main.bundleURL.path, reply: finished)
            }
        }
        let allowed: Set<String> = [
            "native_operation_returned_unverified",
            "native_operation_returned_unverified_transport_recovered",
            "native_profile_date_advanced_install_unverified",
            "native_refresh_record_updated_install_unverified",
            "native_selected_team_refresh_returned_install_unverified",
            "native_host_reinstall_returned_install_unverified",
            "native_host_reinstall_owner_unverified",
            // P107: worker replies are finite non-sensitive categories. Do
            // not collapse an exact account/team failure into a generic
            // AppManager error; never authorize a different-team host.
            "selected_account_owner_unverified",
            "selected_account_owner_changed",
            "selected_account_signer_changed",
            "team_operation_in_progress",
            "host_selected_team_mismatch",
            "host_selected_team_certificate_missing",
            "host_bundle_path_unavailable",
            "host_signed_bundle_unavailable", "host_identity_mismatch",
            "host_registration_failed", "host_payload_cache_unavailable",
            "host_cached_bundle_mismatch", "host_team_record_missing",
            "host_managed_owner_mismatch", "host_managed_record_inactive",
            "already_running",
            "anisette_unavailable", "vpn_unavailable", "signing_failed",
            "profile_refresh_failed", "server_unavailable",
            "installation_failed", "sidestore_native_operation_failed",
            "sidestore_database_unavailable", "no_managed_apps",
            "host_not_managed", "host_not_in_refresh_results",
            "no_managed_apps_for_selected_team",
            "managed_apps_inactive_for_selected_team",
            "managed_apps_excluded_from_refresh_for_selected_team",
            "selected_team_inventory_unavailable",
            "selected_team_not_in_refresh_results",
            "selected_team_changed", "selected_team_certificate_missing",
            "selected_team_certificate_activation_failed",
            "selected_team_certificate_readback_failed",
            "sidestore_certificate_missing", "refresh_worker_missing", "transport_unavailable",
            "worker_unresponsive", "pairing_file_missing", "pairing_invalid",
            "minimuxer_not_started", "device_network_unavailable",
            "device_endpoint_unavailable", "sidestore_auth_missing",
            "device_identifier_unavailable", "certificate_expired",
            "certificate_revoked", "profile_missing", "app_group_missing",
            "device_operation_timed_out", "sidestore_invalid_configuration",
            "sidestore_team_mismatch", "sidestore_team_recovery_failed",
                    "sidestore_team_owner_unverified",
                    "sidestore_team_identifier_collision",
                    "sidestore_account_identifier_collision",
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
            status == "native_refresh_record_updated_install_unverified" ||
            status == "native_selected_team_refresh_returned_install_unverified" ||
            // P106 original SideStore AppManager.install returned. This is
            // a worker callback, not proof the iPhone installed a new profile.
            status == "native_host_reinstall_returned_install_unverified"
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
    // P71: P69 boot restored the original SideStore RPPairing at 06:01:24,
    // then a redundant automatic-refresh inspection timed out at 06:01:44.
    // Reuse only a fresh verified, in-process RSD transport result. The
    // actual refresh worker still validates transport again before install.
    private static var lastVerifiedAt: Date?
    private static var inspectionTask: Task<(Bool, String), Never>?

    public static func invalidateInspectionHint() {
        lastVerifiedAt = nil
    }

    public static func inspectForAutomaticRefresh() async -> (Bool, String) {
        if let at = lastVerifiedAt,
           Date().timeIntervalSince(at) >= 0,
           Date().timeIntervalSince(at) < 30 {
            return (true, "pairing_saved_and_transport_ready")
        }
        return await inspectPersistedState()
    }

    public static func inspectPersistedState() async -> (Bool, String) {
        // Settings' initial state check and the foreground renewal check
        // should not occupy the single embedded SideStore worker twice.
        if let inspectionTask { return await inspectionTask.value }
        let task = Task { @MainActor in await inspectFreshPersistedState() }
        inspectionTask = task
        let result = await task.value
        inspectionTask = nil
        if result.0 && result.1 == "pairing_saved_and_transport_ready" {
            lastVerifiedAt = Date()
        } else if result.1 != "pairing_state_read_timeout" &&
                  result.1 != "transport_unavailable" {
            lastVerifiedAt = nil
        }
        return result
    }

    private static func inspectFreshPersistedState() async -> (Bool, String) {
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
        // New pairing data invalidates a recently successful old transport.
        invalidateInspectionHint()
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
    // Replaces a PROVEN dead cached proxy, never an active native refresh.
    // Keep the listener and account/Keychain vault intact: only our owned
    // SideStore LiveProcess and its XPC client are disposed.
    @discardableResult
    func scarletRetireFailedAuthGuest(expected: RefreshClient) -> Bool {
        guard c == nil, launchContinuation == nil,
              let connected = client,
              (connected as AnyObject) === (expected as AnyObject) else {
            return false
        }
        NSLog("[SCARLET_XPC] stale_worker_retired_after_readiness_failure")
        if let ownedExtension = ext { ownedExtension._kill(9) }
        client = nil
        sideStorePid = 0
        ext = nil
        return true
    }

    func scarletEnsureAuthGuest() async throws {
        try await scarletEnsureAuthGuest(allowOrphanRebind: true)
    }

    private func scarletEnsureAuthGuest(allowOrphanRebind: Bool) async throws {
        if let existing = client {
            if sideStorePid > 0 && getpgid(sideStorePid) > 0 { return }
            // An interrupted child may leave a non-nil remoteObjectProxy.
            guard scarletRetireFailedAuthGuest(expected: existing) else {
                throw ScarletNativeAuthError.workerUnavailable
            }
        }
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
            process.setRequestInterruptionBlock { [weak process] _ in
                Task { @MainActor in
                    guard let interrupted = process,
                          self.ext === interrupted else { return }
                    self.client = nil
                    self.sideStorePid = 0
                    self.ext = nil
                    ScarletNativeAuthTransport.shared.cancel()
                }
            }
            let identifier = await process.beginRequest(withInputItems: [request])
            sideStorePid = process.pid(forRequestIdentifier: identifier)
        }
        for _ in 0..<80 {
            if client != nil { return }
            try await Task.sleep(for: .milliseconds(250))
        }
        // The process may still have a PID but never connect to this
        // authenticated XPC listener. Retire this single orphaned native
        // worker only after the full handshake window expired and no native
        // signing/refresh or launch continuation is in progress.
        if allowOrphanRebind, c == nil, launchContinuation == nil,
           client == nil, sideStorePid > 0, getpgid(sideStorePid) > 0 {
            NSLog("[SCARLET_XPC] orphan_worker_rebound_after_no_connection")
            if let orphan = ext { orphan._kill(9) }
            sideStorePid = 0
            ext = nil
            try await scarletEnsureAuthGuest(allowOrphanRebind: false)
            return
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
    public let managed: Bool?
    public let deviceInstalled: Bool?
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
                let status = reason ?? "worker_unknown"
                let successReasons: Set<String> = ["ready", "ready_inventory_unavailable"]
                let failureReasons: Set<String> = [
                    "database_unavailable", "response_too_large", "response_invalid",
                    "slot_worker_missing", "team_operation_in_progress", "selected_account_owner_unverified"
                ]
                // Failure responses cannot publish stale or untrusted rows.
                guard successReasons.contains(status) else {
                    gate.finish([], failureReasons.contains(status) ? status : "worker_unknown"); return
                }
                guard let raw = json, raw.utf8.count <= 64000,
                      let bytes = raw.data(using: .utf8),
                      let rows = try? JSONDecoder().decode([ScarletSideloadSlot].self, from: bytes),
                      rows.count <= 80,
                      Set(rows.map(\.id)).count == rows.count,
                      rows.allSatisfy({ !$0.id.isEmpty && $0.id.utf8.count <= 200 &&
                          $0.name.utf8.count <= 120 &&
                          ($0.managed != false || (!$0.editable && $0.deviceInstalled == true)) }) else {
                    gate.finish([], "response_invalid"); return
                }
                gate.finish(rows, status)
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
                let successReasons: Set<String> = [
                    "side_store_pipeline_returned_device_unverified", "already_in_requested_state"
                ]
                let failureReasons: Set<String> = [
                    "coredata_state_unverified", "active_slot_full", "app_not_managed",
                    "invalid_request", "host_protected", "operation_in_progress",
                    "activation_or_restore_failed", "backup_or_deactivation_failed",
                    "database_unavailable", "slot_worker_missing", "team_operation_in_progress",
                    "selected_account_owner_unverified", "selected_account_app_mismatch"
                ]
                guard (successReasons.contains(status) || failureReasons.contains(status)),
                      ok == successReasons.contains(status) else {
                    gate.finish(false, "worker_unknown"); return
                }
                gate.finish(ok, status)
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


// P102: Decode only fixed categorical Apple portal error evidence from
// the existing authenticated LiveProcess reply. The raw NSError description,
// network URL, Apple ID, Team, P12 and request body never cross this boundary.
public struct ScarletCertificatePortalEvidence: Codable, Sendable {
    public let v: Int
    public let reason: String
    public let stage: String
    public let domain: String
    public let code: Int
    public let underlyingDomain: String
    public let underlyingCode: Int
    public let depth: Int

    public static func decode(_ raw: String) -> ScarletCertificatePortalEvidence? {
        let prefix = "scarlet_certificate_failure:"
        guard raw.hasPrefix(prefix), raw.utf8.count <= 1100,
              let data = String(raw.dropFirst(prefix.count)).data(using: .utf8),
              let item = try? JSONDecoder().decode(Self.self, from: data) else {
            return nil
        }
        let allowedReasons: Set<String> = [
            "selected_team_certificate_portal_failed",
            "selected_team_certificate_quota_reached",
            "selected_team_certificate_new_issue_unconfirmed"
        ]
        let domains: Set<String> = [
            "url", "cocoa", "posix", "osstatus", "appleapi",
            "altserver", "sidestore", "other", "none"
        ]
        guard item.v == 1,
              allowedReasons.contains(item.reason),
              ["import_lookup", "preflight", "create", "readback"].contains(item.stage),
              domains.contains(item.domain),
              domains.contains(item.underlyingDomain),
              (-2_147_483_648...2_147_483_647).contains(item.code),
              (-2_147_483_648...2_147_483_647).contains(item.underlyingCode),
              (0...4).contains(item.depth) else { return nil }
        return item
    }

    public var safeLogFields: [String: String] {
        ["reason": reason, "native_error_stage": stage,
         "native_error_domain": domain, "native_error_code": String(code),
         "native_underlying_domain": underlyingDomain,
         "native_underlying_code": String(underlyingCode),
         "native_error_depth": String(depth)]
    }
}

// R6P66_MULTI_ACCOUNT_TRANSPORT_BEGIN
// Account identities travel only over the authenticated on-device anonymous
// SideStore XPC channel. No password/token is included in these DTOs.
public struct ScarletStoredAppleAccount: Identifiable, Decodable, Sendable {
    public let id: String
    public let active: Bool
    public let teamID: String
    public let certificateReady: Bool
    public let ownerVerified: Bool
    public let managedAppCount: Int
}

@available(iOS 17.0, *)
@MainActor
public enum ScarletNativeSavedAccounts {
    // P102 CI repair: this framework cannot import LiveContainerSwiftUI's
    // ScarletDiagnosticRecorder. Return only bounded diagnostics to its host.
    private static var pendingPortalEvidence: ScarletCertificatePortalEvidence?

    public static func takePortalEvidence() -> ScarletCertificatePortalEvidence? {
        let value = pendingPortalEvidence
        pendingPortalEvidence = nil
        return value
    }

    private static func retainPortalEvidence(_ value: ScarletCertificatePortalEvidence) {
        pendingPortalEvidence = value
    }

    public static func list() async -> (accounts: [ScarletStoredAppleAccount], status: String) {
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return ([], "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else {
            return ([], "transport_unavailable")
        }
        return await withCheckedContinuation { c in
            let gate = ScarletAccountListGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 15) {
                gate.finish([], "timeout")
            }
            client.scarletAuthAccounts { json, reason in
                guard let value = json,
                      value.utf8.count <= 8192,
                      let data = value.data(using: .utf8),
                      let accounts = try? JSONDecoder().decode(
                        [ScarletStoredAppleAccount].self, from: data),
                      accounts.count <= 8,
                      accounts.allSatisfy({
                          $0.id.utf8.count <= 254 && $0.teamID.utf8.count == 10 &&
                          (0...999).contains($0.managedAppCount)
                      }) else {
                    gate.finish([], "response_invalid"); return
                }
                let known = ["ready", "keychain_write_failed", "keychain_read_failed",
                             "response_invalid", "account_worker_missing"]
                let reason = reason ?? "worker_unknown"
                gate.finish(accounts, known.contains(reason) ? reason : "worker_unknown")
            }
        }
    }

    // Per-Team SideInstaller-style P12 import: only the selected Apple ID's
    // active Team can receive this archive in the embedded SideStore Keychain.
    // The host certificate and unrelated Apple Team certificates stay intact.
    public static func importSelectedTeamCertificate(
        _ archive: Data, password: String, teamID: String) async -> (Bool, String) {
        pendingPortalEvidence = nil
        guard archive.count > 0 && archive.count <= 10_000_000,
              password.utf8.count <= 1024 else {
            return (false, "invalid_p12_import_request")
        }
        let (accounts, status) = await list()
        guard status == "ready", accounts.filter({ $0.active }).count == 1,
              accounts.contains(where: { $0.active && $0.teamID == teamID }) else {
            return (false, "selected_team_changed")
        }
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return (false, "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else {
            return (false, "transport_unavailable")
        }
        return await withCheckedContinuation { c in
            let gate = ScarletAccountActivationGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 90) {
                gate.finish(false, "timeout_state_unknown")
            }
            client.scarletImportInstallCertificate(
                archive, password: password, teamID: teamID) { ok, reason in
                let known = ["imported_selected_team", "ready_existing",
                    "invalid_p12_import_request", "selected_team_changed",
                    "authentication_in_progress", "team_operation_in_progress",
                    "account_worker_missing", "p12_decode_or_password_invalid",
                    "p12_wrong_team_or_expired", "p12_not_registered_with_selected_team",
                    "selected_team_certificate_portal_failed",
                    "selected_team_certificate_storage_failed",
                    "selected_account_signer_binding_failed",
                    "selected_account_owner_unverified",
                    "selected_account_owner_changed",
                    "selected_team_certificate_readback_failed",
                    "sidestore_team_mismatch", "sidestore_team_recovery_failed",
                    "sidestore_team_owner_unverified",
                    "sidestore_team_identifier_collision",
                    "sidestore_account_identifier_collision",
                    "sidestore_auth_missing"]
                let raw = reason ?? "worker_unknown"
                let evidence = ok ? nil : ScarletCertificatePortalEvidence.decode(raw)
                let result = evidence?.reason ?? raw
                let accepted = ok && (result == "imported_selected_team" ||
                    result == "ready_existing")
                let outcome = known.contains(result) ? result : "worker_unknown"
                if let evidence {
                    Task { @MainActor in
                        retainPortalEvidence(evidence)
                        gate.finish(accepted, outcome)
                    }
                } else {
                    gate.finish(accepted, outcome)
                }
            }
        }
    }

    public static func prepareInstallTeam(_ teamID: String) async -> (Bool, String) {
        await teamOperation(teamID, issue: false)
    }

    public static func issueInstallCertificate(_ teamID: String) async -> (Bool, String) {
        await teamOperation(teamID, issue: true)
    }

    // UI-only manual fresh issuance: never accepts a reused portal P12.
    public static func issueFreshInstallCertificate(_ teamID: String) async -> (Bool, String) {
        await teamOperation(teamID, issue: true, forceFresh: true)
    }

    // This call never selects a second Apple ID. It obtains a cert only on
    // an explicit account activation/login/install action, then re-reads
    // the authoritative SideStore Keychain and active team.
    public static func ensureSelectedTeamCertificate(_ teamID: String) async -> (Bool, String) {
        let initial = await prepareInstallTeam(teamID)
        if initial.0 { return (true, "ready_existing") }
        guard initial.1 == "selected_team_certificate_missing" else { return initial }
        let issued = await issueInstallCertificate(teamID)
        guard issued.0 else { return issued }
        let confirmed = await prepareInstallTeam(teamID)
        return confirmed.0 ? issued : (false, "selected_team_certificate_readback_failed")
    }

    private static func teamOperation(_ teamID: String, issue: Bool,
                                      forceFresh: Bool = false) async -> (Bool, String) {
        pendingPortalEvidence = nil
        guard teamID.utf8.count == 10 && teamID.allSatisfy({
            $0.isASCII && ($0.isUppercase || $0.isNumber)
        }) else { return (false, "invalid_team") }
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return (false, "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else {
            return (false, "transport_unavailable")
        }
        return await withCheckedContinuation {
            (c: CheckedContinuation<(Bool, String), Never>) in
            let gate = ScarletAccountActivationGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + (issue ? 180 : 30)) {
                gate.finish(false, "timeout_state_unknown")
            }
            let callback: (Bool, String?) -> Void = { ok, status in
                let known = ["ready", "selected_team_changed", "invalid_team",
                             "authentication_in_progress", "account_worker_missing",
                             "selected_team_certificate_missing",
                             "selected_team_certificate_activation_failed",
                             "selected_team_certificate_readback_failed",
                             "selected_team_certificate_unverified",
                             "selected_team_certificate_portal_failed",
                             "selected_team_certificate_quota_reached",
                             "selected_team_certificate_storage_failed",
                             "selected_account_owner_unverified",
                             "selected_account_owner_changed",
                             "selected_account_signer_binding_failed",
                             "selected_team_certificate_new_issue_not_created",
                             "selected_team_certificate_new_issue_unconfirmed",
                             "ready_existing_portal", "ready_issued_apple",
                             "sidestore_team_mismatch", "sidestore_team_recovery_failed",
                    "sidestore_team_owner_unverified",
                    "sidestore_team_identifier_collision",
                    "sidestore_account_identifier_collision",
                             "sidestore_auth_missing", "transport_unavailable",
                             "team_operation_in_progress"]
                let raw = status ?? "worker_unknown"
                let evidence = ok ? nil : ScarletCertificatePortalEvidence.decode(raw)
                let reason = evidence?.reason ?? raw
                let success = forceFresh
                    ? reason == "ready_issued_apple"
                    : (reason == "ready" ||
                       (issue && (reason == "ready_existing_portal" ||
                                  reason == "ready_issued_apple")))
                let accepted = ok && success
                let outcome = known.contains(reason) ? reason : "worker_unknown"
                if let evidence {
                    Task { @MainActor in
                        retainPortalEvidence(evidence)
                        gate.finish(accepted, outcome)
                    }
                } else {
                    gate.finish(accepted, outcome)
                }
            }
            if forceFresh {
                client.scarletIssueFreshInstallTeamCertificate(teamID, reply: callback)
            } else if issue {
                client.scarletIssueInstallTeamCertificate(teamID, reply: callback)
            } else {
                client.scarletPrepareInstallTeam(teamID, reply: callback)
            }
        }
    }

    public static func activate(_ id: String) async -> (Bool, String) {
        guard id.utf8.count > 3 && id.utf8.count <= 254 else {
            return (false, "invalid_request")
        }
        do { try await ScarletNativeAuthTransport.shared.prepare() }
        catch { return (false, "transport_unavailable") }
        guard let client = RefreshHandler.shared.client else {
            return (false, "transport_unavailable")
        }
        let result = await withCheckedContinuation {
            (c: CheckedContinuation<(Bool, String), Never>) in
            let gate = ScarletAccountActivationGate(c)
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
                gate.finish(false, "timeout_state_unknown")
            }
            client.scarletSelectAuthAccount(id) { ok, reason in
                let known = ["active_team_verified", "keychain_unavailable",
                             "keychain_write_failed", "account_not_found",
                             "current_session_unverified", "account_activation_unverified",
                             "invalid_request", "authentication_in_progress",
                             "account_worker_missing", "rollback_unverified",
                             "team_operation_in_progress"]
                let status = reason ?? "worker_unknown"
                gate.finish(ok && status == "active_team_verified",
                    known.contains(status) ? status : "worker_unknown")
            }
        }
        if result.0 { ScarletNativeAuthTransport.shared.scarletAccountWasSwitched() }
        return result
    }
}

private final class ScarletAccountListGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<
        (accounts: [ScarletStoredAppleAccount], status: String), Never>?
    init(_ c: CheckedContinuation<
        (accounts: [ScarletStoredAppleAccount], status: String), Never>) {
        continuation = c
    }
    func finish(_ rows: [ScarletStoredAppleAccount], _ status: String) {
        lock.lock(); let c = continuation; continuation = nil; lock.unlock()
        c?.resume(returning: (rows, status))
    }
}
private final class ScarletAccountActivationGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<(Bool, String), Never>?
    init(_ c: CheckedContinuation<(Bool, String), Never>) { continuation = c }
    func finish(_ ok: Bool, _ status: String) {
        lock.lock(); let c = continuation; continuation = nil; lock.unlock()
        c?.resume(returning: (ok, status))
    }
}
// R6P66_MULTI_ACCOUNT_TRANSPORT_END
