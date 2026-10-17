#!/usr/bin/env python3
"""V33: apply PR#4-equivalent increased-memory capability support to pinned SideSign.

Scope: SideSign AppIDs/Feature/DeveloperPortalAPI only. Do not touch certificates,
Apple credentials, app IDs belonging to other teams, or preexisting entitlements.
No requests are made by this build-time patch. Runtime only operates on a user
requested app whose signing entitlements explicitly request the capability.
"""
from pathlib import Path
import sys

MARKER = "NRG_V33_FREE_MEMORY_CAPABILITY_V1"
FILES = (
    "Sources/Models/Feature.swift",
    "Sources/DeveloperPortal/AppIDs.swift",
    "Sources/DeveloperPortal/DeveloperPortalAPI.swift",
)


def once(s, before, after):
    if s.count(before) != 1:
        raise ValueError(f"pinned SideSign anchor changed ({s.count(before)} hits): {before[:80]}")
    return s.replace(before, after, 1)


def transform(original: dict[str, str]) -> dict[str, str]:
    f = original[FILES[0]]
    a = original[FILES[1]]
    p = original[FILES[2]]
    if all(MARKER in x for x in (f, a, p)):
        if any(x.count(MARKER) != 1 for x in (f, a, p)):
            raise ValueError("duplicate V33 memory capability")
        return dict(original)
    if any(MARKER in x for x in (f, a, p)):
        raise ValueError("partially applied V33 memory capability")

    f = once(f, "    static let freeFeatures: Set<Feature> = [",
        '''    // NRG_V33_FREE_MEMORY_CAPABILITY_V1: Apple enables this on Personal Teams,
    // but the developer services v1 bundleIdCapabilities PATCH is mandatory.
    var capabilityID: String? {
        self == .increasedMemoryLimit ? "INCREASED_MEMORY_LIMIT" : nil
    }

    static let freeFeatures: Set<Feature> = [''')
    f = once(f, '''        .appGroups,
        .interAppAudio
    ]

    static let paidFeatures''', '''        .appGroups,
        .interAppAudio,
        .increasedMemoryLimit
    ]

    static let paidFeatures''')

    a = once(a, '''        for (feature, value) in appID.features {
            let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)''',
        '''        // NRG_V33_FREE_MEMORY_CAPABILITY_V1: separate Apple's v1 capability
        // IDs from the legacy updateAppId.action feature dictionary.
        var capabilities: [String] = []
        for (feature, value) in appID.features {
            if let id = feature.capabilityID {
                if value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "true" {
                    capabilities.append(id)
                }
                continue
            }
            let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)''')
    a = once(a, '''        verboseLog("[SideSign] Updated: \\(updatedAppID.name) (\\(updatedAppID.bundleIdentifier))")
        return updatedAppID''',
        '''        verboseLog("[SideSign] Updated: \\(updatedAppID.name) (\\(updatedAppID.bundleIdentifier))")
        // Fail visibly if Apple refuses the requested memory capability:
        // reporting a successful installation without the entitlement would
        // falsely imply Playport has increased RAM. Never silently bypass it.
        if !capabilities.isEmpty {
            try await enableCapabilities(capabilities.sorted(), for: updatedAppID,
                                         team: team, session: session)
        }
        return updatedAppID''')
    tail = '''    func deleteAppID(_ appID: AppID, for team: Team, session: Session) async throws -> Bool {'''
    capability = '''    // NRG_V33_FREE_MEMORY_CAPABILITY_V1: PR SideStore/SideSign#4, the
    // Apple developer services v1 endpoint, not legacy updateAppId.action.
    func enableCapabilities(_ capabilityIDs: [String], for appID: AppID,
                            team: Team, session: Session) async throws {
        guard !capabilityIDs.isEmpty else { return }
        // No arbitrary capabilities: only the capability explicitly supported
        // on free teams and selected from signed app entitlements.
        guard capabilityIDs.allSatisfy({ $0 == "INCREASED_MEMORY_LIMIT" }) else {
            throw ServerError.badServerResponse(reason: "Unexpected capability", jsonPayload: "")
        }
        let capabilities: [[String: Any]] = capabilityIDs.map { id in [
            "type": "bundleIdCapabilities",
            "attributes": ["enabled": true, "settings": [Any]()],
            "relationships": [
                "capability": ["data": ["id": id, "type": "capabilities"]]
            ]
        ] }
        let body: [String: Any] = ["data": [
            "id": appID.identifier,
            "type": "bundleIds",
            "attributes": [
                "name": appID.name, "identifier": appID.bundleIdentifier,
                "teamId": team.identifier, "seedId": team.identifier,
                "bundleType": "bundle", "hasExclusiveManagedCapabilities": false
            ],
            "relationships": ["bundleIdCapabilities": ["data": capabilities]]
        ]]
        var request = URLRequest(url: URL(
            string: "bundleIds/\\(appID.identifier)", relativeTo: servicesBaseURL)!)
        request.httpMethod = "PATCH"
        request.httpBody = try JSONSerialization.data(withJSONObject: body,
                                                       options: [.sortedKeys])
        let _: EmptyResponse = try await sendServicesBodyRequest(request, session: session)
        debugLog("[NRG_MEMORY_CAPABILITY] stage=developerPortal result=enabled")
    }

'''
    a = once(a, tail, capability+tail)

    if not p.endswith("\n}\n"):
        raise ValueError("unexpected SideSign DeveloperPortalAPI file end")
    function = '''    // NRG_V33_FREE_MEMORY_CAPABILITY_V1: direct JSON:API PATCH as Xcode and
    // GetMoreRam use. Never print authentication or response payloads.
    func sendServicesBodyRequest<T: Decodable>(_ originalRequest: URLRequest,
                                               session apiSession: Session) async throws -> T {
        var request = originalRequest
        let h = customHeaders
        let a = apiSession.anisetteData
        let headers: [String: String] = [
            "Content-Type": "application/vnd.api+json",
            "User-Agent": h.developerServices.userAgent,
            "Accept": "application/vnd.api+json",
            "Accept-Language": "en-us",
            "X-Apple-App-Info": h.grandSlam.authApp,
            "X-Xcode-Version": apiSession.xcodeVersion,
            "X-Apple-I-Identity-Id": apiSession.dsid,
            "X-Apple-GS-Token": apiSession.authToken,
            "X-Apple-I-MD-M": a.machineID,
            "X-Apple-I-MD": a.oneTimePassword,
            "X-Apple-I-MD-LU": a.localUserID,
            "X-Apple-I-MD-RINFO": a.routingInfo,
            "X-Mme-Device-Id": a.deviceID,
            "X-MMe-Client-Info": a.clientInfo,
            "X-Apple-I-Client-Time": a.clientTime,
            "X-Apple-Locale": a.locale,
            "X-Apple-I-Locale": a.locale,
            "X-Apple-I-TimeZone": a.timeZone
        ]
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
        // Delegate to the existing URLSession; no new identity or auth flow.
        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            // Only numeric HTTP status is propagated: no Apple account data.
            throw ServerError.underlyingError(code: status,
                message: "Apple Developer Services capability request failed")
        }
        if data.isEmpty, let empty = EmptyResponse() as? T { return empty }
        if let response = try? JSONDecoder().decode(T.self, from: data) {
            return response
        }
        throw ServerError.invalidResponseFormat(rawPayload: "[redacted capability response]")
    }
'''
    p = p[:-2] + function + "}\n"
    return {FILES[0]: f, FILES[1]: a, FILES[2]: p}


def patch(root: Path) -> None:
    before = {name: (root/name).read_text(encoding="utf-8") for name in FILES}
    after = transform(before)
    if transform(after) != after:
        raise ValueError("V33 SideSign transform not idempotent")
    for name in FILES:
        if before[name] != after[name]:
            (root/name).write_text(after[name], encoding="utf-8")
    print("[PATCH] V33 Apple free-team Increased Memory Limit support prepared")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v33_memory_capability.py <pinned-SideSign-dir>")
    patch(Path(sys.argv[1]))
