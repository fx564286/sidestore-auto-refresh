#!/usr/bin/env python3
"""V27: avoid exhausting free-team App IDs on optional extensions.

Scoped to fresh installations on free Apple teams with extension customization
disabled; edits only the already-staged temporary IPA app bundle. Existing
installed apps, re-installs, host extensions, signing identities and certs are
not touched. The existing removal and manifest cleanup methods are reused.
"""
from pathlib import Path
import sys

MARKER = "NRG_V27_FREE_TEAM_EXTENSIONS"

def patch(root: Path) -> None:
    p = root / "SideStore/Core/Operations/PipelineOperations/RemoveAppExtensionsOperation.swift"
    if not p.is_file():
        raise SystemExit(f"[FAIL] missing {p}")
    s = p.read_text()
    if MARKER in s:
        if s.count(MARKER) != 1:
            raise SystemExit("[FAIL] duplicate V27 marker")
        print("[PASS] V27 free-team extension removal already applied")
        return
    before = """        self.setProgress(30)
        let excessExtensions = processExtensionsInfo(from: targetAppBundle, localAppExtensions: localAppExtensions)"""
    after = r"""        // NRG_V27_FREE_TEAM_EXTENSIONS: a fresh app with several optional
        // extensions may exceed Apple's free-team 10-App-ID weekly quota.
        // Only modify this temporary install candidate, never an installed app.
        // Preserve the explicit customization handler when user enabled it.
        if let team = AuthManager.shared.team,
           team.type == .free,
           localAppExtensions == nil,
           !UserDefaults.standard.customizeAppExtensions {
            let extensionCount = targetAppBundle.appExtensions.count
            debugLog("[NRG_V27_FREE_TEAM] action=remove_optional_extensions scope=fresh_staged_install count=\(extensionCount)")
            try self.removeExtensions(from: targetAppBundle.appExtensions, endPercent: 85)
            try self.updateManifest()
            self.setProgress(100)
            return targetAppBundle
        }

        self.setProgress(30)
        let excessExtensions = processExtensionsInfo(from: targetAppBundle, localAppExtensions: localAppExtensions)"""
    if s.count(before) != 1:
        raise SystemExit(f"[FAIL] expected one pinned anchor, found {s.count(before)}")
    s=s.replace(before,after,1)
    if s.count(MARKER)!=1 or s.count("try self.updateManifest()")!=2:
        raise SystemExit("[FAIL] V27 postcondition")
    p.write_text(s)
    print("[PASS] V27 staged fresh-app extensions removed for free team; user customization preserved")

if __name__ == "__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v27_free_team_extensions.py <EmbeddedSideStore>")
    patch(Path(sys.argv[1]))
