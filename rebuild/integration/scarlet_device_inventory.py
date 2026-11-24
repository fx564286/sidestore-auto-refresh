"""Read-only installation_proxy inventory for the pinned minimuxer sources."""
from pathlib import Path

def patch_device_inventory(engine: Path) -> None:
    base = engine / "Dependencies/minimuxer/DeviceGateway"
    def replace(path, old, new):
        source = path.read_text()
        if source.count(old) != 1:
            raise RuntimeError(f"P127 pinned inventory anchor mismatch: {path}")
        path.write_text(source.replace(old, new, 1))

    api = base / "DeviceGatewayAPI.swift"
    replace(api, "public protocol DeviceGatewayAPI:", """public struct ScarletDeviceInventoryRow: Sendable {
    public let id: String
    public let name: String
    public let developmentSigned: Bool
    public init(id: String, name: String, developmentSigned: Bool) {
        self.id = id
        self.name = name
        self.developmentSigned = developmentSigned
    }
}

public protocol DeviceGatewayAPI:""")
    replace(api, "    func fetchUDID() async throws -> String",
        "    func scarletDeviceInventory() async throws -> [ScarletDeviceInventoryRow]\n    func fetchUDID() async throws -> String")
    replace(api, "public extension DeviceGatewayAPI {", """public extension DeviceGatewayAPI {
    func scarletDeviceInventory() async throws -> [ScarletDeviceInventoryRow] {
        throw DeviceGatewayError(.unsupportedOperation, reason: "scarlet_device_inventory")
    }
""")
    idevice = base / "idevice/IdeviceGateway.swift"
    replace(idevice, "    public func fetchUDID() async throws -> String {", """    public func scarletDeviceInventory() async throws -> [ScarletDeviceInventoryRow] {
        try await withFFIDispatch {
            try self.performWithEitherService(
                connectRP: installation_proxy_connect_rsd,
                connectLockdown: installation_proxy_connect,
                cleanup: installation_proxy_client_free,
                serviceName: "instproxy"
            ) { client in
                var result: UnsafeMutableRawPointer?
                var count = 0
                let error = "User".withCString {
                    installation_proxy_get_apps(client, $0, nil, 0, &result, &count)
                }
                if let error {
                    defer { idevice_error_free(error) }
                    throw DeviceGatewayError(.serviceError, reason: "scarlet_inventory_lookup_failed")
                }
                guard count > 0 else { return [] }
                guard let result else {
                    throw DeviceGatewayError(.serviceError, reason: "scarlet_inventory_invalid")
                }
                let nodes = result.assumingMemoryBound(to: plist_t?.self)
                defer {
                    for i in 0..<count { self.safeFreePlist(nodes[i]) }
                    free(result)
                }
                guard count <= 4096 else {
                    throw DeviceGatewayError(.serviceError, reason: "scarlet_inventory_too_large")
                }
                return (0..<count).compactMap { i in
                    guard let node = nodes[i] else { return nil }
                    func string(_ key: String) -> String? {
                        key.withCString { key in
                            guard let value = plist_dict_get_item(node, key) else { return nil }
                            return self.getRustPlistString(value)
                        }
                    }
                    guard let id = string("CFBundleIdentifier"), !id.isEmpty else { return nil }
                    let name = string("CFBundleDisplayName") ?? string("CFBundleName") ?? id
                    let signer = string("SignerIdentity") ?? ""
                    var debug: UInt8 = 0
                    if let entitlements = plist_dict_get_item(node, "Entitlements"),
                       let flag = plist_dict_get_item(entitlements, "get-task-allow") {
                        plist_get_bool_val(flag, &debug)
                    }
                    return ScarletDeviceInventoryRow(id: id, name: name,
                        developmentSigned: debug != 0 || signer.hasPrefix("Apple Development:") ||
                            signer.hasPrefix("iPhone Developer:"))
                }
            }
        }
    }

    public func fetchUDID() async throws -> String {""")

    lib = base / "libimobiledevice/LibimobiledeviceGateway.swift"
    replace(lib, "    public func fetchUDID() async throws -> String {", """    public func scarletDeviceInventory() async throws -> [ScarletDeviceInventoryRow] {
        try await withFFIDispatch {
            guard self.pairingFileType == .rppairing else {
                throw DeviceGatewayError(.unsupportedOperation, reason: "scarlet_inventory_legacy_backend")
            }
            return try self.withRSDService(.installationProxy) { stream in
                try self.rsdSendPlist(stream, dict: [
                    "Command": "Lookup",
                    "ClientOptions": ["ApplicationType": "User"]
                ])
                let response = try self.rsdRecvPlist(stream)
                guard let apps = response["LookupResult"] as? [String: [String: Any]],
                      apps.count <= 4096 else {
                    throw DeviceGatewayError(.serviceError, reason: "scarlet_inventory_invalid")
                }
                return apps.compactMap { id, app in
                    let name = app["CFBundleDisplayName"] as? String ??
                        app["CFBundleName"] as? String ?? id
                    let signer = app["SignerIdentity"] as? String ?? ""
                    let entitlements = app["Entitlements"] as? [String: Any]
                    return ScarletDeviceInventoryRow(id: id, name: name,
                        developmentSigned: entitlements?["get-task-allow"] as? Bool == true ||
                            signer.hasPrefix("Apple Development:") || signer.hasPrefix("iPhone Developer:"))
                }
            }
        }
    }

    public func fetchUDID() async throws -> String {""")
