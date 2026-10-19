#!/usr/bin/env python3
"""V57: align in-app OTA host identity with signed NRG and show real build numbers.

Edits only the builder's canonical Swift templates before patch_v3_unified_shell
copies them into the pinned sources. Never removes bundle matching or signs an IPA.
"""
from pathlib import Path
import sys

SHELL = Path("scripts/templates/v3_unified_shell.swift")
SERVICE = Path("scripts/templates/v3_sidestore_service.swift")
MARK = "NRG_V57_OTA_SELF_IDENTITY"


def one(text: str, original: str, replacement: str, label: str) -> str:
    count = text.count(original)
    if count != 1:
        raise RuntimeError(f"V57 {label}: expected one anchor, found {count}")
    return text.replace(original, replacement, 1)


def patch_shell(text: str) -> str:
    if MARK in text:
        if (text.count(MARK) < 3 or r'Text("#\(current)")' not in text or
                r'Label("빌드 #\(build.version) 다운로드 및 설치"' not in text or
                'hostEntry.bundleID == signedHostID' not in text):
            raise RuntimeError("V57 OTA self-identity patch is partial")
        return text

    # V55 had accidentally escaped Swift's interpolation backslash.
    text = one(text, r'Text("#\\(current)")',
               r'Text("#\(current)")', "current build number")
    text = one(text, r'Label("빌드 #\\(build.version) 다운로드 및 설치"',
               r'Label("빌드 #\(build.version) 다운로드 및 설치"',
               "candidate build number")

    old = '''            guard let host = Bundle.main.bundleIdentifier,
                  status.installedApps.contains(where: { $0.isHost && $0.bundleID == host }) else {
                throw NSError(domain: "NRGOTA", code: 3)
            }
            guard status.connected, !status.needsSignIn, !status.loading else {
                throw NSError(domain: "NRGOTA", code: 4)
            }
            note = "SHA-256 체크섬 확인 중…"'''
    new = '''            // ''' + MARK + ''': check the *actual installed bundle ID*, not
            // the embedded SideStore library's legacy "isHost" classification.
            // A LiveProcess entry point may expose the extension bundle ID.
            let runningID = Bundle.main.bundleIdentifier ?? ""
            let signedHostID = runningID.hasSuffix(".LiveProcess")
                ? String(runningID.dropLast(".LiveProcess".count))
                : runningID
            guard current > 0, !signedHostID.isEmpty else {
                NSLog("[NRG_V57_OTA] stage=self_identity result=failed reason=invalid_running_bundle")
                throw NSError(domain: "NRGOTA", code: 3)
            }
            guard status.connected, !status.needsSignIn, !status.loading else {
                throw NSError(domain: "NRGOTA", code: 4)
            }
            // A stale read must not be mistaken for an absent host; refresh once,
            // then still refuse installation unless a matching active row exists.
            if !status.installedApps.contains(where: { $0.bundleID == signedHostID && $0.isActive }) {
                _ = await status.reloadAndWait(manual: true)
            }
            guard let hostEntry = status.installedApps.first(where: {
                $0.bundleID == signedHostID && $0.isActive
            }), hostEntry.bundleID == signedHostID else {
                NSLog("[NRG_V57_OTA] stage=self_identity result=failed reason=installed_host_not_matched count=%d",
                      status.installedApps.count)
                throw NSError(domain: "NRGOTA", code: 3)
            }
            NSLog("[NRG_V57_OTA] stage=self_identity result=pass host_match=1 legacy_isHost=%d sequence=%d",
                  hostEntry.isHost ? 1 : 0, current)
            note = "SHA-256 체크섬 확인 중…"'''
    text = one(text, old, new, "self-update identity gate")

    old_catch = '''        } catch {
            note = "업데이트 중단 (단계 코드: \((error as NSError).code)). SideStore 연결 및 서명을 확인해."
            NSLog("[NRG_V52_OTA] stage=prepare result=failed candidate=%d",candidate.version)
        }
    }
}'''
    new_catch = '''        } catch {
            // ''' + MARK + ''': a missing database identity is not a pairing failure.
            let code = (error as NSError).code
            switch code {
            case 3:
                note = "앱 자체 ID가 SideStore 설치 목록과 일치하지 않아 중단했어. Apps에서 NRG 설치 상태를 확인해."
            case 4:
                note = "SideStore 연결·로그인 또는 작업 준비 상태를 확인해."
            default:
                note = "업데이트 중단 (단계 코드: \(code)). 설치 전 준비 상태를 확인해."
            }
            NSLog("[NRG_V57_OTA] stage=prepare result=failed candidate=%d code=%d",
                  candidate.version, code)
        }
    }
}'''
    text = one(text, old_catch, new_catch, "stage-specific error wording")
    return text


def patch_service(text: str) -> str:
    # Service-side isHost is used by Installed Apps and JIT flows too; the
    # embedded runtime is part of LiveContainer, not a standalone SideStore app.
    new_marker = "NRG_V57_OTA_SERVICE_HOST_ID"
    if new_marker in text:
        if text.count(new_marker) != 1 or "Bundle.main.bundleIdentifier" not in text:
            raise RuntimeError("V57 service host predicate partially patched")
        return text
    old = '''                     "isHost": app.bundleIdentifier == StoreApp.altstoreAppID] as [String: Any]'''
    new = '''                     // ''' + new_marker + ''': recognize the signed NRG host,
                     // while preserving upstream SideStore's original host ID.
                     "isHost": app.bundleIdentifier == StoreApp.altstoreAppID ||
                               app.bundleIdentifier == Bundle.main.bundleIdentifier] as [String: Any]'''
    return one(text, old, new, "embedded SideStore host classifier")


def main(root: Path) -> None:
    patches = [(root / SHELL, patch_shell), (root / SERVICE, patch_service)]
    pending = []
    for path, patch in patches:
        before = path.read_text(encoding="utf-8")
        after = patch(before)
        if patch(after) != after:
            raise RuntimeError(f"V57 transform is not idempotent: {path}")
        pending.append((path, before, after))
    for path, before, after in pending:
        if before != after:
            path.write_text(after, encoding="utf-8")
        print(f"[PASS] V57 OTA host identity/template: {path.relative_to(root)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v57_ota_identity.py <builder-root>")
    main(Path(sys.argv[1]))
