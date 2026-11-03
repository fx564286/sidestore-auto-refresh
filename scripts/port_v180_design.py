#!/usr/bin/env python3
"""Forward-port Scarlet Crystal's *real* user-authored UI patches.

Each legacy transformer still validates its exact source anchors and is
applied on an isolated checkout. The old SHA-only guards are bypassed only
after verifying BOTH of the current coherent upstream git commits. Never
replace failing patches with stock UI or silent no-op markers.
"""
from pathlib import Path
import importlib
import json
import subprocess
import shutil
import sys
import re



def port_current_sidestore_service_primitives(side: Path) -> None:
    """Restore exact upstream types and the canonical credential transaction.

    No stored credentials, provisioning profiles, guest containers or user
    preference values are modified. Patch the disposable build checkout only.
    """
    key = side / "AltStore/Core/Components/Keychain.swift"
    prefs = side / "AltStore/Core/Extensions/UserDefaults+AltStore.swift"
    source_dialog = side / "SideStore/DeepLinks/InstallAppDialog.swift"
    app = side / "AltStore/AppDelegate.swift"
    for file in (key, prefs, source_dialog, app):
        if not file.is_file():
            raise ValueError("V181 SideStore runtime source missing: " + str(file))

    canonical = importlib.import_module("patch_embedded_keychain")
    key_text = key.read_text()
    source_marker = "LC_EMBEDDED_SHARED_KEYCHAIN_V1"
    if source_marker not in key_text:
        fixes = [
            ("import Foundation\n",
             "import Foundation\nimport Security\n#if canImport(Darwin)\nimport Darwin\n#elseif canImport(Glibc)\nimport Glibc\n#endif\n"),
            ("KeychainAccess.Keychain(service: Bundle.Info.appbundleIdentifier)\n"
             "                                            .accessibility(.afterFirstUnlock)\n"
             "                                            .synchronizable(true)",
             "LCEmbeddedSharedKeychain.makeClient()"),
            ("case is Data.Type: return try? Keychain.shared.keychain.getData(self.key) as? Value",
             "case is Data.Type: return LCEmbeddedSharedKeychain.read(self.key, client: Keychain.shared.keychain) as? Value"),
            ("case is String.Type: return try? Keychain.shared.keychain.getString(self.key) as? Value",
             "case is String.Type: return LCEmbeddedSharedKeychain.readString(self.key, client: Keychain.shared.keychain) as? Value"),
            ("case is Data.Type: Keychain.shared.keychain[data: self.key] = newValue as? Data",
             "case is Data.Type: LCEmbeddedSharedKeychain.write(self.key, data: newValue as? Data, client: Keychain.shared.keychain)"),
            ("case is String.Type: Keychain.shared.keychain[self.key] = newValue as? String",
             "case is String.Type: LCEmbeddedSharedKeychain.write(self.key, data: (newValue as? String).map { Data($0.utf8) }, client: Keychain.shared.keychain)"),
            ("        self.migrateLegacyKeychainItems()",
             "        LCEmbeddedSharedKeychain.prepare(self.keychain)\n"
             "        if LCEmbeddedSharedKeychain.isReady(self.keychain) { self.migrateLegacyKeychainItems() }"),
            ('get { try? self.keychain.getData("importedCert_" + serial) }',
             'get { LCEmbeddedSharedKeychain.read("importedCert_" + serial, client: self.keychain) }'),
            ('            if let data = newValue {\n'
             '                try? self.keychain.set(data, key: "importedCert_" + serial)\n'
             '            } else {\n'
             '                try? self.keychain.remove("importedCert_" + serial)\n'
             '            }',
             '            LCEmbeddedSharedKeychain.write("importedCert_" + serial, data: newValue, client: self.keychain)'),
            ("        try? self.keychain.removeAll()",
             "        LCEmbeddedSharedKeychain.clearAll(self.keychain)"),
        ]
        for before, after in fixes:
            key_text = canonical.once(key_text, before, after)
        key_text += ("\n" + canonical.TEMPLATE.read_text()
                     + "\n" + canonical.KEYCHAIN_ACCESS_ADAPTER + "\n")
    elif (canonical.TEMPLATE.read_text() not in key_text or
          canonical.KEYCHAIN_ACCESS_ADAPTER not in key_text):
        raise ValueError("V181 shared Keychain adapter was only partially restored")

    # The original enum resides in InstallAppDialog, a deliberately excluded
    # UI file. Preserve every original preference case and exact raw value.
    dialog_text = source_dialog.read_text()
    enum_start = "public enum AppImportSourceMode: String, CaseIterable, Identifiable, Sendable {"
    enum_end = "\n@MainActor\npublic enum InstallAppDialog"
    if dialog_text.count(enum_start) != 1 or dialog_text.count(enum_end) != 1:
        raise ValueError("SideStore import-source enum changed upstream")
    enum_body = dialog_text[dialog_text.index(enum_start):dialog_text.index(enum_end)]
    pref_text = prefs.read_text()
    enum_marker = "// SCARLET_V181_RETAIN_IMPORT_SOURCE_ENUM"
    if enum_marker not in pref_text:
        if "public enum AppImportSourceMode:" in pref_text:
            raise ValueError("AppImportSourceMode already defined in retained settings")
        pref_text += "\n" + enum_marker + "\n" + enum_body + "\n"
    elif enum_body not in pref_text:
        raise ValueError("partially retained original import-source enum")

    # Current CoreData requires an explicit managed-object context.
    # Only the source getter changes, never the active team or account.
    app_text = app.read_text()
    team_before = "DatabaseManager.shared.activeTeam()?.identifier"
    team_after = ("DatabaseManager.shared.activeTeam(in: "
                  "DatabaseManager.shared.persistentContainer.viewContext)?.identifier")
    if team_before in app_text:
        app_text = app_text.replace(team_before, team_after)
    elif team_after not in app_text:
        raise ValueError("embedded active-team lookup drifted")

    # The same modern context signature applies to health snapshots.
    # Never fabricate an account/team when the persisted CoreData object is absent.
    for before, after in (
        ("DatabaseManager.shared.activeAccount()?.appleID",
         "DatabaseManager.shared.activeAccount(in: DatabaseManager.shared.persistentContainer.viewContext)?.appleID"),
        ("let team = DatabaseManager.shared.activeTeam()",
         "let team = DatabaseManager.shared.activeTeam(in: DatabaseManager.shared.persistentContainer.viewContext)"),
    ):
        if before in app_text:
            app_text = app_text.replace(before, after)
        elif after not in app_text:
            raise ValueError("health snapshot query changed in modern SideStore")

    # Modern ImportExport.importAccount became async; maintain exact source
    # import semantics instead of skipping or silently reporting success.
    import_before = "static func accountImport(token: String, password: String) throws -> [String: Any]"
    import_after = "static func accountImport(token: String, password: String) async throws -> [String: Any]"
    call_before = "let account = try ImportExport.importAccount(data, filePassword: password)"
    call_after = "let account = try await ImportExport.importAccount(data, filePassword: password)"
    if import_before in app_text:
        if app_text.count(import_before) != 1 or app_text.count(call_before) != 1:
            raise ValueError("embedded account import changed upstream")
        app_text = app_text.replace(import_before, import_after)
        app_text = app_text.replace(call_before, call_after)
    elif import_after not in app_text or call_after not in app_text:
        raise ValueError("embedded account import async forwarding missing")

    # SideStore and SideStoreSupport are separate Swift modules; the
    # identical typed, privacy-filtered failure contract must compile in each.
    failure_path = side / "SideStore/Core/CombinedFailure.swift"
    failure_body = (Path(__file__).resolve().parent /
                    "templates/combined_failure.swift").read_text()
    if "public struct CombinedFailure: Error, LocalizedError {" not in failure_body:
        raise ValueError("canonical typed failure contract unavailable")
    if failure_path.exists() and failure_path.read_text() != failure_body:
        raise ValueError("different SideStore typed failure contract already exists")

    # Current SideStore portal API is intentionally identity-bound in
    # patch_v3_service.py. Add the scoped tracing adapters referenced there,
    # without embedding account/team/bundle IDs or provider text in the wire.
    portal_path = side / "SideStore/Core/Auth/LCDeveloperPortalSigningContext.swift"
    portal_body = """// SCARLET_V181_TYPED_PORTAL_SIGNING_CONTEXT
import Foundation
import CryptoKit

private func lcPortalFingerprint(_ value: String) -> String {
    SHA256.hash(data: Data(value.utf8))
        .map { String(format: "%02x", $0) }.joined()
}

func lcPortalSigningContext(
    teamID: String, generation: UInt64,
    bundleID: String? = nil, features: [String: Any]? = nil,
    groupCount: Int? = nil, groupID: String? = nil,
    profileMode: String? = nil
) -> [String: String] {
    var facts: [String: String] = ["session_generation": String(generation)]
    if !teamID.isEmpty { facts["team_sha256"] = lcPortalFingerprint(teamID) }
    if let bundleID, !bundleID.isEmpty {
        facts["requested_bundle_sha256"] = lcPortalFingerprint(bundleID)
    }
    if let groupID, !groupID.isEmpty {
        facts["requested_app_group_sha256"] = lcPortalFingerprint(groupID)
    }
    if let groupCount, groupCount >= 0 {
        facts["app_group_count"] = String(groupCount)
    }
    if let features {
        facts["capability_count"] = String(features.count)
        let names = features.keys.sorted()
        if names.count <= 32, Set(names).isSubset(of: CombinedFailure.signingCapabilityNames) {
            facts["capability_names"] = names.joined(separator: ",")
        }
    }
    if let profileMode, ["team", "manual"].contains(profileMode) {
        facts["profile_mode"] = profileMode
    }
    return CombinedFailure.validatedSigningContext(facts) ?? [:]
}

func lcPortalSigningRequest<T>(
    sourceStep: String,
    facts: [String: String],
    operation: () async throws -> T
) async throws -> T {
    do {
        return try await operation()
    } catch {
        if error is CancellationError { throw error }
        if let known = error as? CombinedFailure { throw known }
        let native = error as NSError
        let metadata: [String: Any] = [
            "LCStructuredFailureStageV1": CombinedFailure.Stage.signing.rawValue,
            "LCStructuredFailureSourceV1": sourceStep,
            "LCStructuredSigningContextV1":
                CombinedFailure.validatedSigningContext(facts) ?? [:],
            NSUnderlyingErrorKey: native
        ]
        // Original domain/code remain available to the fixed-classifier.
        // Only explicitly allowlisted structured fields enter the wire.
        let classified = NSError(domain: native.domain, code: native.code,
                                 userInfo: metadata)
        throw CombinedFailure.capture(classified, operation: "sign",
                                      stage: .signing, id: UUID().uuidString)
    }
}
"""
    if portal_path.exists() and portal_path.read_text() != portal_body:
        raise ValueError("existing SideStore portal signing adapter differs")
    if ("func lcPortalSigningRequest<T>(" not in portal_body or
            "CombinedFailure.validatedSigningContext(facts)" not in portal_body):
        raise ValueError("incomplete typed portal helper")

    # Upstream PipelineRunner now expects the already-existing CoreData
    # context, rather than a legacy StandaloneOperationContext wrapper.
    # Keep the exact same transaction and cancellation gate.
    pipeline_call_fixes = (
        ("performSingleOperation(operation, handler: handler, context: context)",
         "performSingleOperation(operation, handler: handler, dbContext: context.dbBackgroundContext)"),
        (".deleteApp(app), handler: handler, context: context",
         ".deleteApp(app), handler: handler, dbContext: context.dbBackgroundContext"),
    )
    for before, after in pipeline_call_fixes:
        if before in app_text:
            if app_text.count(before) != 1:
                raise ValueError("multiple headless pipeline operation call sites")
            app_text = app_text.replace(before, after)
        elif after not in app_text:
            raise ValueError("V181 headless pipeline operation source drifted")

    # Upstream RefreshGroup now owns a CoreData context directly and keeps
    # its failure in group.error. Preserve the exact refresh transaction,
    # cancellation hook, outcome verification and existing persisted data.
    refresh_group_fixes = (
        ("let group = RefreshGroup(context: baseContext)",
         "let group = RefreshGroup(dbContext: baseContext.dbBackgroundContext)"),
        ("group.context.error = error", "group.error = error"),
    )
    for before, after in refresh_group_fixes:
        if before in app_text:
            if app_text.count(before) != 1:
                raise ValueError("ambiguous headless refresh-group compatibility patch")
            app_text = app_text.replace(before, after)
        elif app_text.count(after) != 1:
            raise ValueError("headless refresh-group API drifted from reviewed upstream")

    # File-import notifications belong to the old standalone UI. Their
    # payload constants remain stable without depending on stripped AppDelegate.
    file_import = side / "SideStore/DeepLinks/FileImportHandler.swift"
    file_import_text = file_import.read_text()
    notification_substitutions = (
        ("AppDelegate.importAppDeepLinkNotification",
         "Notification.Name(Bundle.Info.appbundleIdentifier + \".ImportAppDeepLinkNotification\")"),
        ("AppDelegate.importAppDeepLinkURLKey", "\"fileURL\""),
    )
    for before, after in notification_substitutions:
        if before in file_import_text:
            file_import_text = file_import_text.replace(before, after)
        elif after not in file_import_text:
            raise ValueError("headless file-import notification drifted")

    # The standalone onboarding screen still exists upstream but the single
    # host-owned login flow is V3HeadlessAuthHandler, not the removed legacy
    # UIKit sign-in API. Explicitly reject this unreachable obsolete entry.
    onboarding = side / "SideStore/Views/Onboarding/OnboardingView.swift"
    onboarding_text = onboarding.read_text()
    legacy_login = """_ = try await AuthManager.shared.signIn(
                                presentingViewController: UIApplication.shared.topViewController(),
                                skipResign: true,
                                skipHowTos: true
                            )"""
    headless_login = """throw V3SideStoreServiceError.unsupported // Headless: use host-owned auth flow"""
    if legacy_login in onboarding_text:
        if onboarding_text.count(legacy_login) != 1:
            raise ValueError("ambiguous onboarding old auth entry")
        onboarding_text = onboarding_text.replace(legacy_login, headless_login)
    elif headless_login not in onboarding_text:
        raise ValueError("unrecognized standalone onboarding auth entry")

    # Match the actual SideStore Nov-2026 async and CoreData contracts.
    # Sign-out still preserves the same user-requested signing certificate
    # and anisette data, and import retains its transactional identity fence.
    modern_service_calls = (
        ("AuthManager.shared.signOut(keepCertificate: true, keepAnisetteData: true)",
         "await AuthManager.shared.signOut(keepCertificate: true, keepAnisetteData: true)"),
        ("return try V3BackendCommands.accountImport(token: target, password: password)",
         "return try await V3BackendCommands.accountImport(token: target, password: password)"),
        ("let storedTeam = DatabaseManager.shared.activeTeam()",
         "let storedTeam = DatabaseManager.shared.activeTeam(in: context)"),
        ("let storedAccount = DatabaseManager.shared.activeAccount()",
         "let storedAccount = DatabaseManager.shared.activeAccount(in: context)"),
    )
    for before, after in modern_service_calls:
        if before in app_text:
            if app_text.count(before) != 1:
                raise ValueError("multiple SideStore async/managed-context API call sites")
            app_text = app_text.replace(before, after)
        elif app_text.count(after) != 1:
            raise ValueError("SideStore async/managed-context API drift")

    # The new Apple 2FA flow reports an optional error string on
    # TwoFactorRequest, not the removed TwoFactorVerificationFailure type.
    # Never forward Apple-controlled raw error text across the XPC bridge.
    two_factor_fixes = (
        ("failure: TwoFactorVerificationFailure?) async throws -> TwoFactorResponse",
         "failure: String?) async throws -> TwoFactorResponse"),
        ("failure?.userMessage ?? V3TwoFactorRetryPolicy.recoveryMessage(authFailureKind: priorKind) ?? acknowledgement",
         '(failure != nil ? "The verification code was not accepted. Enter a new code." : ' +
         '(V3TwoFactorRetryPolicy.recoveryMessage(authFailureKind: priorKind) ?? acknowledgement))'),
        ("failure: .unknown)", 'failure: "missing_code")'),
    )
    for before, after in two_factor_fixes:
        if before in app_text:
            if app_text.count(before) != 1:
                raise ValueError("ambiguous V3 two-factor API migration")
            app_text = app_text.replace(before, after)
        elif app_text.count(after) != 1:
            raise ValueError("SideStore 2FA signature changed upstream")
    two_factor_old = "failure: request.verificationFailure"
    two_factor_new = "failure: request.error"
    if two_factor_old in app_text:
        if app_text.count(two_factor_old) != 3:
            raise ValueError("unexpected number of V3 2FA delivery arms")
        app_text = app_text.replace(two_factor_old, two_factor_new)
    elif app_text.count(two_factor_new) != 3:
        raise ValueError("new SideStore two-factor error projection missing")

    # AuthManager intentionally keeps the live session and team private.
    # Only this read-only, same-file adapter lets V3 verify that provisioning
    # retry belongs to the saved account. It never synthesizes a token.
    auth_file = side / "SideStore/Core/Auth/AuthManager.swift"
    auth_source = auth_file.read_text()
    auth_adapter = """
// SCARLET_V181_READONLY_AUTH_IDENTITY_V1
extension AuthManager {
    var v3CachedSessionForResume: ALTAppleAPISession? { self.session }
    var v3CachedTeamAppleIDForResume: String? { self.team?.account?.appleID }
}
"""
    if "SCARLET_V181_READONLY_AUTH_IDENTITY_V1" not in auth_source:
        if auth_source.count("private var session: ALTAppleAPISession?") != 1 or (
                auth_source.count("private var team: ALTTeam?") != 1):
            raise ValueError("private SideStore live auth state moved")
        auth_source += auth_adapter
    elif auth_adapter not in auth_source:
        raise ValueError("partial auth read adapter")
    private_auth_refs = (
        ("let session = auth.session", "let session = auth.v3CachedSessionForResume"),
        ("let teamOwner = auth.team?.account?.appleID",
         "let teamOwner = auth.v3CachedTeamAppleIDForResume"),
        ("let teamAppleID = AuthManager.shared.team?.account?.appleID",
         "let teamAppleID = AuthManager.shared.v3CachedTeamAppleIDForResume"),
    )
    for before, after in private_auth_refs:
        if before in app_text:
            if app_text.count(before) != 1:
                raise ValueError("ambiguous V3 identity read")
            app_text = app_text.replace(before, after)
        elif app_text.count(after) != 1:
            raise ValueError("V3 identity retry binding changed")

    # Four historic OperationError enum cases disappeared in the modern
    # SideStore API. Remove impossible switch arms, retain the typed cases
    # that still exist, and conservatively return the existing unknown case.
    operation_guidance = "func v3OperationErrorGuidance(_ error: OperationError)"
    if app_text.count(operation_guidance) != 1:
        raise ValueError("typed operation guidance missing")
    start = app_text.index(operation_guidance)
    finish = app_text.index("\n}\n", start) + 2
    guidance = app_text[start:finish]
    obsolete_operation_cases = (
        "certificateChanged", "provisioningError",
        "maximumAppIDLimitReached", "connectionFailed"
    )
    for member in obsolete_operation_cases:
        pattern = (r"(?m)^    case \." + member +
                   r":\n        return \([^\n]+\n                [^\n]+\n")
        guidance, removed = re.subn(pattern, "", guidance)
        if removed != 1:
            raise ValueError("SideStore operation enum changed for " + member)
    app_text = app_text[:start] + guidance + app_text[finish:]

    # Current SignInHandler adds explicit skip notices and a device retry
    # decision. Route notices through the already-supported host dialog;
    # a device-registration failure may retry/cancel, never silently skip.
    auth_methods = """
    // SCARLET_V181_CURRENT_SIGNIN_PROTOCOL_V1
    func resolveDeviceRegistrationErrors(_ error: Error) async -> ProvisioningErrorDecision {
        return await resolveProvisioningError(error)
    }

    func showCertificateSkipAcknowledgment() async {
        _ = try? await ask(kind: "postAuth", title: "Certificate Provisioning Skipped",
                           message: "No signing certificate was installed. Installing or refreshing apps requires a usable signing certificate.",
                           options: [["id": "continue", "label": "Continue"]])
    }

    func showDeviceRegistrationSkipAcknowledgment() async {
        _ = try? await ask(kind: "postAuth", title: "Device Registration Skipped",
                           message: "This device has not been registered. App provisioning may not work until registration succeeds.",
                           options: [["id": "continue", "label": "Continue"]])
    }

"""
    auth_end = "    func complete() async {}\n"
    if "SCARLET_V181_CURRENT_SIGNIN_PROTOCOL_V1" not in app_text:
        if app_text.count(auth_end) != 1:
            raise ValueError("V3 headless authentication protocol extension anchor changed")
        app_text = app_text.replace(auth_end, auth_methods + auth_end)
    elif auth_methods not in app_text:
        raise ValueError("partial SignInHandler protocol migration")

    # New profile/plist/icon/entitlement callbacks are optional user choices.
    # nil means exactly 'do not alter the signed app' on current SideStore,
    # preserving the original install, signing and profile pipeline.
    customization_methods = """
    // SCARLET_V181_CURRENT_CUSTOMIZATION_PROTOCOL_V1
    func resolveInfoPlistCustomization(
        targets: [InfoPlistTarget], initialBundleID: String,
        appendTeamID: Bool, installedAppIdentities: [String: String],
        teamID: String
    ) async throws -> (modifiedPlists: [String: [String: any Sendable]], appendTeamID: Bool)? {
        return nil
    }

    func resolveInfoPlistCustomization(
        initialPlist: [String: any Sendable], initialBundleID: String,
        appendTeamID: Bool, installedAppIdentities: [String: String],
        teamID: String
    ) async throws -> (modifiedPlist: [String: any Sendable], appendTeamID: Bool)? {
        return nil
    }

    func resolveEntitlementsCustomization(
        targets: [EntitlementsTarget], teamType: ALTTeamType
    ) async throws -> [String: [String: any Sendable]]? {
        return nil
    }

    func resolveEntitlementsCustomization(
        initialEntitlements: [String: any Sendable], bundleID: String,
        teamType: ALTTeamType
    ) async throws -> [String: any Sendable]? {
        return nil
    }

    func resolveAppIconCustomization(appName: String) async throws -> URL? {
        return nil
    }

    func resolveProvisioningProfileCustomization(
        appName: String, bundleID: String
    ) async throws -> ProfileCustomizationChoice? {
        return nil
    }

"""
    customization_anchor = "    func resolveAppGroupMismatch(originalGroup: String, correctedGroup: String) async throws -> AppGroupResolution {"
    if "SCARLET_V181_CURRENT_CUSTOMIZATION_PROTOCOL_V1" not in app_text:
        if app_text.count(customization_anchor) != 1:
            raise ValueError("V3 headless pipeline customization source changed")
        app_text = app_text.replace(customization_anchor,
                                    customization_methods + customization_anchor)
    elif customization_methods not in app_text:
        raise ValueError("partial user customization compatibility")

    # Validate all pending edits before writing any file to the checkout.
    expected = ("LCEmbeddedAuthenticationSnapshot", "func authenticationSnapshot() throws",
                "LCEmbeddedSharedKeychain.makeClient()")
    if any(term not in key_text for term in expected) or enum_body not in pref_text:
        raise ValueError("V181 preserved credential/preference type is incomplete")
    key.write_text(key_text)
    prefs.write_text(pref_text)
    app.write_text(app_text)
    auth_file.write_text(auth_source)
    file_import.write_text(file_import_text)
    onboarding.write_text(onboarding_text)
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    portal_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.write_text(failure_body)
    portal_path.write_text(portal_body)


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: port_v180_design.py <LiveContainer> <EmbeddedSideStore> <pins.json>")
    live, side, pin_path = map(lambda x: Path(x).resolve(), sys.argv[1:])
    pins = json.loads(pin_path.read_text())
    expected = {"LIVE_CONTAINER_REF", "EMBEDDED_SIDESTORE_REF",
                "MINIMUXER_REF", "SIDESIGN_REF"}
    if set(pins) != expected:
        raise ValueError("upstream source graph is not the reviewed four-key graph")
    for root, key in ((live, "LIVE_CONTAINER_REF"), (side, "EMBEDDED_SIDESTORE_REF")):
        sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                      text=True).strip()
        if sha != pins[key]:
            raise ValueError(f"upstream provenance mismatch: {key}")
    path = Path(__file__).resolve().parent
    sys.path.insert(0, str(path))
    def report(name, action):
        print(f"[SCARLET_V180] applying prior user UI overlay: {name}", flush=True)
        action()
        print(f"[SCARLET_V180] verified overlay: {name}", flush=True)

    # Historical dependency order; do not rebuild UI from stock.
    report("host guest return", lambda: importlib.import_module("patch_guest_return").patch(live))
    for name in (
        "patch_v76_native_guest_switcher",
        "patch_v75_retained_guest_reconcile",
        "patch_v86_verified_dead_guest_reconcile",
        "patch_dead10cc_fix",
    ):
        report(name, lambda n=name: subprocess.run(
            [sys.executable, str(path / (n + ".py")), str(live)], check=True))
    report("user dock geometry", lambda: importlib.import_module("patch_multitask_dock").patch(live))
    for name in (
        "patch_v27_guest_switch",
        "patch_v28_guest_lifecycle",
        "patch_v46_keyboard_window_scope",
        "patch_v47_resume",
        "patch_v28_pip_audio",
    ):
        report(name, lambda n=name: subprocess.run(
            [sys.executable, str(path / (n + ".py")), str(live)], check=True))
    # Legacy layout transformer uses a fixed pin for its generated manifest.
    # Rebind only that provenance constant to the separately verified current
    # parent; ALL visual source/anchor checks in the transformer still run.
    app_layout = importlib.import_module("patch_app_layout")
    app_layout.LIVE_CONTAINER_REVISION = pins["LIVE_CONTAINER_REF"]
    report("user app grid", lambda: app_layout.patch_livecontainer(live, v3_grid=True))
    report("user unified shell", lambda: importlib.import_module("patch_v3_unified_shell").patch(live, side))
    # The original V3 service owns account/refresh commands and on-device
    # WirelessPair RPC. Use audited parent SHAs and fail on source drift.
    report("original V3 JIT-Less certificate diagnosis", lambda: subprocess.run(
        [sys.executable, str(path / "patch_v32_jitless_diagnosis.py"), str(live)],
        check=True))
    v3_service = importlib.import_module("patch_v3_service")
    v3_service.PINS = (pins["LIVE_CONTAINER_REF"], pins["EMBEDDED_SIDESTORE_REF"])
    report("V3 account/refresh/command service and pairing RPC", lambda:
           v3_service.patch(live, side))
    # The modern SideStore standalone Xcode target treats every nested
    # *.imageset/*.appiconset file in the obsolete Icons.xcassets tree as a
    # flat copied resource, producing duplicate PNG and Contents.json outputs.
    # This is the *embedded SideStore* checkout, not LiveContainer's host.
    # Keep original bytes in a non-target directory instead of deleting them.
    old_icons = side / "AltStore/Resources/Icons.xcassets"
    archived_icons = side / ".scarlet-retained-upstream-icons/Icons.xcassets"
    if old_icons.is_dir() and not old_icons.is_symlink():
        if archived_icons.exists():
            raise ValueError("old SideStore icon archive already exists")
        archived_icons.parent.mkdir(parents=True, exist_ok=True)
        old_icons.rename(archived_icons)
        # Standalone SideStore still requires one named AppIcon catalog. Keep
        # the *original* AppIcon.appiconset byte-for-byte, without importing
        # the alternate image/icon sets that flatten to duplicate output paths.
        primary = archived_icons / "AppIcon.appiconset"
        if not primary.is_dir() or primary.is_symlink():
            raise ValueError("original SideStore AppIcon.appiconset is unavailable")
        old_icons.mkdir(parents=True, exist_ok=False)
        shutil.copytree(primary, old_icons / "AppIcon.appiconset")
        print("[SCARLET_V181] retained original AppIcon only; archived all alternate icons", flush=True)
    elif archived_icons.is_dir() and not old_icons.exists():
        print("[SCARLET_V181] embedded SideStore stock icons already retained", flush=True)
    else:
        raise ValueError("expected embedded SideStore stock icon catalog is missing or unsafe")
    # This exact original account Form row was previously installed by the
    # large pinned V3 command patch; preserve it without replaying obsolete
    # SideStore auth transport against the newer selected sources.
    report("original V3 account + JIT settings", lambda: subprocess.run(
        [sys.executable, str(path / "patch_v181_v3_settings_port.py"), str(live)],
        check=True))
    # The canonical V129/V134 JIT scripts were authored against the
    # verified V49/V50 PID URLComponents and base64 wire-format adapters.
    # Restore these actual earlier transformations before the V55–V170 UI
    # chain; otherwise later scripts have no matching source and cannot
    # distinguish script-name from executable script-data.
    for name in ("patch_v49_auto_jit", "patch_v50_stikdebug_protocol"):
        report(name, lambda n=name: subprocess.run(
            [sys.executable, str(path / (n + ".py")), str(live)], check=True))

    # The historical user's visual/interaction layer, reapplied in dependency
    # order as recorded in the original V176 combined build. This is NOT stock
    # LiveContainer UI, and patch errors are surfaced rather than ignored.
    visual_scripts = ["patch_v34_display_profiles","patch_v36_multitask_chrome","patch_v37_window_overflow","patch_v38_maximized_safe_area","patch_v39_dock_app_switch_only","patch_v41_remove_floating_return","patch_v55_rotation_geometry","patch_v56_notch_ui","patch_v58_fullscreen","patch_v58_native_activity","patch_v60_island_guest_switch","patch_v192_startup","patch_v72_overflow_longpress","patch_v73_apple_floating_control","patch_v97_retained_guest_host_rebind","patch_v100_morph_guest_switcher","patch_v100_native_guest_morph","patch_v102_guest_recent_coherence","patch_v102_unified_window_actions","patch_v102_retire_native_gestures","patch_v103_single_guest_control","patch_v104_guest_scene_reactivation","patch_v105_delete_legacy_return","patch_v107_retire_dead_return_settings","patch_v108_remove_blue_collapsed_dock","patch_v110_single_guest_dock","patch_v129_jit_viewport","patch_v131_reference_liquid_glass","patch_v132_glass_drag_one_owner","patch_v133_keyboard_focus_handoff","patch_v134_jit_protocol","patch_v135_restore_jit_provider","patch_v136_rotation_atomic","patch_v137_rotation_glass_owner","patch_v138_functional_guest_control","patch_v139_unified_touch_glass","patch_v139_landscape_video_viewport","patch_v140_glass_morph","patch_v141_inset_settle","patch_v141_outside_tap","patch_v143_guest_window_peek","patch_v144_glass_outside","patch_v147_from_v144","patch_v147_direct","patch_v148_action_glass","patch_v149_controls","patch_v150_touch_glass","patch_v151_geometry","patch_v151_glass_polish","patch_v153_three_fixes","patch_v154_three_runtime_fixes","patch_v155_single_liveprocess","patch_v156_panel_size_outside","patch_v157_panel_width","patch_v158_unified_action_glass","patch_v159_panel_height_native_action","patch_v160_outside_visual_parity","patch_v161_compact_outside","patch_v162_panel_scale","patch_v163_button_size_native","patch_v165_first_install_flow","patch_v166_integrated_rp","patch_v167_restore_ondevice_pairing","patch_v170_pairing_ui_context","patch_v169_event_geometry_transport","patch_v170_landscape_only"]
    for script in visual_scripts:
        arguments = [str(live)]
        if script in ("patch_v58_native_activity", "patch_v167_restore_ondevice_pairing"):
            arguments.append(str(side))
        if script == "patch_v169_event_geometry_transport":
            arguments.append("layout")
        report(script, lambda name=script, args=arguments: subprocess.run(
            [sys.executable, str(path / (name + ".py")), *args], check=True))

    # P00: after V167+V170 provide pairing PIN notification,
    # foreground status polling and existing 2FA entry. Do not touch Glass.
    report("P00 pairing-first and inline Apple 2FA integration",
           lambda: subprocess.run([
               sys.executable, str(path / "patch_v182_p00_ondevice_pairing.py"),
               str(live), str(side)], check=True))

    report("latest SideStore credential/import compatibility",
           lambda: port_current_sidestore_service_primitives(side))

    print("[SCARLET_V180] full source-preserving visual patch chain applied")



if __name__ == "__main__":
    main()
