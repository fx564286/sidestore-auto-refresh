#!/usr/bin/env python3
"""V170: preserve the requested on-device pairing command when UI catch is untyped.

No portrait/landscape geometry, pairing data, certificates or VPN settings touched.
Apply after patch_v167_restore_ondevice_pairing.py to the LiveContainer tree.
"""
from pathlib import Path
import sys

REL=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
MARK="SCARLET_V170_PAIR_COMMAND_CONTEXT"

OLD='''        } catch {
            onDevicePairPhase = "failed"
            onDevicePairPin = ""
            onDevicePairDetail = V3FailureGuidance.message(error)
        }
    }
'''

NEW='''        } catch let failure as CombinedFailure {
            // SCARLET_V170_PAIR_COMMAND_CONTEXT: retain the originating
            // command rather than displaying a bare operation=untyped error.
            // Never log the request response, PIN or pairing identity.
            onDevicePairPhase = "failed"
            onDevicePairPin = ""
            onDevicePairDetail = failure.safeMessage + "\\n" + failure.recovery
            NSLog("[SCARLET_V170_PAIR_COMMAND] command=%@ typed=1 stage=%@ code=%@ safe_cause=%@",
                  operation, failure.stage.rawValue, failure.code.rawValue,
                  failure.safeCause?.rawValue ?? "unknown")
        } catch {
            onDevicePairPhase = "failed"
            onDevicePairPin = ""
            onDevicePairDetail = "Pairing command did not provide a typed failure. Check the device connection and copy the safe log."
            NSLog("[SCARLET_V170_PAIR_COMMAND] command=%@ typed=0 stage=command code=failed",
                  operation)
        }
    }
'''


def patch(s: str) -> str:
    if MARK in s:
        if s.count(MARK) != 1 or 'typed=0 stage=command' not in s:
            raise ValueError("partial V170 pairing UI context")
        return s
    if s.count(OLD) != 1 or "SCARLET_V167_ONDEVICE_UI" not in s:
        raise ValueError("V170 expected exact V167 pairing UI handler")
    return s.replace(OLD, NEW, 1)


def apply(root: Path):
    path=root/REL
    if not path.is_file() or path.is_symlink():
        raise ValueError("V170 pairing UI host missing")
    before=path.read_text(encoding="utf-8")
    after=patch(before)
    if patch(after)!=after: raise ValueError("V170 non-idempotent patch")
    if before!=after:path.write_text(after,encoding="utf-8")
    print("[PASS] V170 on-device pairing command context (no orientation edits)")


if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v170_pairing_ui_context.py <LiveContainer>")
    apply(Path(sys.argv[1]))
