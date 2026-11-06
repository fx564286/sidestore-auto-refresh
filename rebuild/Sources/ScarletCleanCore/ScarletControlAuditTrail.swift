import Foundation

/// Host-injected, privacy-safe diagnostic trail for every application control.
/// This is local-only and never includes Apple IDs, passwords, 2FA, tokens,
/// pairing payloads, certificate data, guest names or arbitrary error strings.
public struct ScarletControlAuditEvent: Codable, Equatable, Sendable {
    public let time: Date
    public let action: ScarletControl
    public let state: ScarletActionState
    public let problem: ScarletActionProblem?
}

/// Bounded in-memory ring. The host may render/export sanitized entries in
/// its diagnostics UI; installing this actor does not enable data upload.
public actor ScarletControlAuditTrail {
    private var ring: [ScarletControlAuditEvent] = []
    public let capacity: Int

    public init(capacity: Int = 200) {
        self.capacity = max(1, min(1000, capacity))
    }

    public func record(_ receipt: ScarletActionReceipt) {
        if ring.count >= capacity { ring.removeFirst() }
        ring.append(ScarletControlAuditEvent(
            time: Date(), action: receipt.action, state: receipt.state,
            problem: receipt.problem))
    }

    public func snapshot() -> [ScarletControlAuditEvent] {
        ring
    }

    public func exportJSON() throws -> Data {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(ring)
    }

    public func clear() {
        ring.removeAll()
    }
}
