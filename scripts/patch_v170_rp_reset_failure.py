#!/usr/bin/env python3
"""V170 RP reset classification: preserve pairing and expose safe recovery.

Apply after V169 transport patches. A TCP probe alone cannot verify an
authenticated RemotePairing tunnel. Only after V164 has exhausted its bounded
attempts AND the terminal handshake is still a reset, tag that terminal error
with the fixed structured failure vocabulary. No re-pair, record modification,
credential reset, alternate trust bypass, or orientation change.
"""
from pathlib import Path
import sys

MARKER = "SCARLET_V170_RP_HANDSHAKE_RESET"
RELATIVE = Path("SideStore/Core/DeviceApi/MinimuxerWrapper.swift")


def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or "remotePairingHandshakeReset" not in source or "SCARLET_V171_RP_RESET_CONTAINMENT" not in source:
            raise ValueError("V170 RemotePairing patch partially applied")
        return source
    for required in ("SCARLET_V164_TRANSPORT_RESYNC",
                     "SCARLET_V169_NO_VPN_PEER_FALLBACK",
                     "remotePairingPortCache = initialPort"):
        if required not in source:
            raise ValueError("V170 expected V169 source is missing " + required)
    start = source.index("private func withRemotePairingRetry<T>(")
    end = source.index("\npublic var minimuxerStatusPublisher:", start)
    segment = source[start:end]
    old = """        throw lastError
    }
}
"""
    if segment.count(old) != 1:
        raise ValueError("V170 unexpected V164 tail")
    new = """        // SCARLET_V170_RP_HANDSHAKE_RESET: the observed final failure
        // followed bounded, authenticated RP attempts. A successful TCP
        // probe is not proof of a working authenticated tunnel. Report only
        // the fixed category, never raw remote errors or private material.
        let terminalTransport = String(describing: lastError).lowercased()
        if transientReset &&
           (terminalTransport.contains("connection reset") ||
            terminalTransport.contains("connectionreset")) {
            NSLog("[SCARLET_V170_RP] stage=transport outcome=reset_after_bounded_retry record=preserved")
            throw NSError(domain: NSPOSIXErrorDomain, code: 54, userInfo: [
                NSLocalizedDescriptionKey: "RemotePairing handshake reset before device identity verification.",
                "LCStructuredFailureStageV1": "pairing",
                "LCStructuredFailureCauseV1": "remotePairingHandshakeReset"
            ])
        }
        throw lastError
    }
}
"""
    # V171: a persistent RST must not spawn an endless sequence of repeated
    # handshakes. Gate only terminal resets for 15 seconds; all original
    # authenticated transport paths remain available after the cooldown.
    # No pairing, VPN, signing, or container state is changed.
    v171_gate = """
// SCARLET_V171_RP_RESET_CONTAINMENT: temporary process-local RST cooldown.
private final class ScarletV171RPResetGate: @unchecked Sendable {
    static let shared = ScarletV171RPResetGate()
    private let lock = NSLock()
    private var retryAfter = Date.distantPast
    func shouldBackOff() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return Date() < retryAfter
    }
    func noteTerminalReset() {
        lock.lock()
        defer { lock.unlock() }
        retryAfter = Date().addingTimeInterval(15)
    }
}

"""
    # Match the stable function declaration, not the presence of an
    # immediate do/catch. Unit fixtures and real generated source differ.
    v171_entry = "private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {"
    v171_entry_new = """private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
    if ScarletV171RPResetGate.shared.shouldBackOff() {
        NSLog("[SCARLET_V171_RP] stage=transport decision=backoff record=preserved")
        throw NSError(domain: NSPOSIXErrorDomain, code: 54, userInfo: [
            NSLocalizedDescriptionKey: "RemotePairing reset. Use Pair on This iPhone if it persists.",
            "LCStructuredFailureStageV1": "pairing",
            "LCStructuredFailureCauseV1": "remotePairingHandshakeReset"
        ])
    }"""
    result = source[:start] + segment.replace(old, new, 1) + source[end:]
    if result.count(v171_entry) != 1:
        raise ValueError("V171 expected one RP function entry")
    result = result.replace(v171_entry, v171_entry_new, 1)
    v171_terminal = '            NSLog("[SCARLET_V170_RP] stage=transport outcome=reset_after_bounded_retry record=preserved")'
    if result.count(v171_terminal) != 1:
        raise ValueError("V171 expected one terminal RP reset")
    result = result.replace(v171_terminal,
        '            ScarletV171RPResetGate.shared.noteTerminalReset()\n' + v171_terminal, 1)
    gate_anchor = "\npublic var minimuxerStatusPublisher:"
    if result.count(gate_anchor) != 1:
        raise ValueError("V171 missing source declaration anchor")
    return result.replace(gate_anchor, "\n" + v171_gate + "public var minimuxerStatusPublisher:", 1)


def apply(root: Path):
    path = root / RELATIVE
    if not path.is_file() or path.is_symlink():
        raise ValueError("V170 expected embedded SideStore source missing")
    original = path.read_text(encoding="utf-8")
    result = patch(original)
    if patch(result) != result:
        raise ValueError("V170 patch not idempotent")
    if original != result:
        path.write_text(result, encoding="utf-8")
    print("[PASS] V170 bounded RP reset classification; pairing record untouched")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v170_rp_reset_failure.py <EmbeddedSideStore>")
    apply(Path(sys.argv[1]))
