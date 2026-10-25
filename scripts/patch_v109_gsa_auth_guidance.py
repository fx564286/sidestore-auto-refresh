#!/usr/bin/env python3
"""V109: show a bounded Apple -80045 Anisette remediation message.

Runs after NRG V98. Never logs credentials, changes Apple/ADI identity,
retries SRP, resets keychains or alters guest/signing state. A human must
choose a compatible provider/profile using the existing SideStore settings.
"""
from pathlib import Path
import sys

FILE = Path("SideStore/Handlers/SignInFlowHandler.swift")
MARKER = "SCARLET_V109_GSA_80045_USER_GUIDANCE"

OLD = """            case .failure(let error):
                completionHandler(.failure(error))
"""
NEW = """            case .failure(let error):
                // SCARLET_V109_GSA_80045_USER_GUIDANCE: the Apple GrandSlam
                // init endpoint returned a server-side rejection, not proof
                // of incorrect credentials, pairing, or device registration.
                // Do not expose raw Apple errors, retry, reset ADI, or sign out.
                if case ServerError.underlyingError(let code, _) = error,
                   code == -80045 {
                    let explanation = NSLocalizedString(
                        "Apple sign-in was rejected during Anisette handshake (-80045). " +
                        "Try a compatible trusted Anisette provider and client profile " +
                        "in SideStore Settings > Advanced > User Customizations. " +
                        "Restart Scarlet Crystal after a profile change. " +
                        "Your certificate, pairing, apps and account data were not removed.",
                        comment: "Anisette profile mismatch; no credential retry")
                    let actionable = NSError(
                        domain: "ScarletCrystal.AnisetteGrandSlam",
                        code: -80045,
                        userInfo: [NSLocalizedDescriptionKey: explanation])
                    completionHandler(.failure(actionable))
                } else {
                    completionHandler(.failure(error))
                }
"""

def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count(NEW) != 1 or OLD in source:
            raise ValueError("V109 partial or drifted sign-in guidance")
        return source
    if source.count(OLD) != 1 or "import SideSign" not in source:
        raise ValueError("V109 pinned sign-in handler changed; no rewrite")
    return source.replace(OLD, NEW, 1)

def apply(root: Path) -> None:
    target = root / FILE
    if not target.is_file() or target.is_symlink():
        raise ValueError("V109 sign-in handler missing")
    before = target.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise ValueError("V109 sign-in guidance non-idempotent")
    if before != after:
        target.write_text(after, encoding="utf-8")
    print("[PASS] V109 bounded -80045 Anisette guidance, credentials and ADI intact")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v109_gsa_auth_guidance.py <embedded-SideStore>")
    apply(Path(sys.argv[1]))
