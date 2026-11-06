#!/usr/bin/env python3
"""Evidence-based Scarlet Crystal release readiness, not a marketing pass.

A standalone SwiftUI typecheck, mock simulator screenshot or static Figma
source check NEVER certifies original native Liquid Glass, pairing or install.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]

def assess(root:Path)->dict:
    manifest=json.loads((root/"rebuild/design/figma-measured-baseline.json").read_text())
    ui=(root/"rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
    audit_path=root/"rebuild/Sources/ScarletCleanCore/ScarletControlAuditTrail.swift"
    host=root/"rebuild/HostApp"
    host_files=list(host.rglob("*")) if host.exists() else []
    host_source="\n".join(p.read_text(errors="replace")
                          for p in host_files if p.is_file() and p.suffix in (".swift",".m",".mm"))
    checks=[]
    def add(id:str,status:str,why:str,release_required=True):
        checks.append(dict(id=id,status=status,evidence=why,releaseRequired=release_required))
    six=len(manifest["screens"])==6
    add("figma_layer_baseline","passed" if six else "failed",
        "Six actual editable Figma screen IDs and measured geometry recorded; no live change webhook configured",
        False)
    anchors=all((s["codeSection"] is None or s["codeSection"] in ui)
                for s in manifest["screens"])
    add("figma_to_swiftui_source_parity","passed" if anchors else "failed",
        "Named screen sections mapped; typecheck and static text test required. Pixel-by-pixel renderer comparison outstanding",
        False)
    add("independent_control_audit","implemented_not_connected" if audit_path.exists()
        else "blocked",
        "Privacy-safe bounded action receipt actor exists; no real Scarlet host invokes or exports it yet")
    native="UIGlassEffect" in host_source and "isInteractive" in host_source
    add("original_native_liquid_glass","blocked" if not native else "source_present_device_unverified",
        "No verifiable original native UIGlassEffect host/gesture integration in new HostApp source"
        if not native else "Source references UIGlassEffect; original-runtime checksum and physical gesture verification still required")
    # The host entrypoint is pinned upstream, not an App.swift file in
    # rebuild/HostApp. Inspect the actual injection adapter instead of falsely
    # reporting a missing host when its source integration is already present.
    injector=root/"rebuild/integration/apply_scarlet_host.py"
    injection_source=injector.read_text(errors="replace") if injector.is_file() else ""
    host_wired=("ScarletIntegratedHostView()" in injection_source
                and "LiveContainerSwiftUI/App/LiveContainerSwiftUIApp.swift" in injection_source
                and "ScarletIntegratedHostView.swift" in injection_source
                and (host/"ScarletIntegratedHostView.swift").is_file())
    add("livecontainer_host_integration",
        "source_present_device_unverified" if host_wired else "blocked",
        "New host is wired through pinned LiveContainer app-entry injection; "
        "paired-engine Xcode archive evidence is checked in its separate CI run, "
        "not in this source-only report; iPhone execution unverified"
        if host_wired else "LiveContainer app-entry injection is missing")
    native_glass_file=host/"ScarletNativeGlass.swift"
    glass_source=native_glass_file.read_text(errors="replace") if native_glass_file.exists() else ""
    glass_wired=(host_wired and "SCNativeLiquidGlassSurface" in glass_source
                 and "UIGlassEffect" in glass_source
                 and "ScarletNativeGlassTabBar" in glass_source)
    add("native_glass_tab_and_switcher",
        "source_present_device_unverified" if glass_wired else "blocked",
        "Native glass tab and guest switcher source are injected; original optical "
        "and touch behavior still need physical iPhone verification"
        if glass_wired else "Native glass tab/switcher source binding is missing")
    switcher=host/"ScarletGuestSwitcherOverlay.swift"
    switcher_source=switcher.read_text(errors="replace") if switcher.exists() else ""
    gesture_source=(host_wired and "SCARLET_GUEST_OUTSIDE_TAP_DISMISS" in switcher_source
                    and "onTapGesture { closeSwitcher() }" in switcher_source)
    add("window_manager_gestures",
        "partially_implemented_device_unverified" if gesture_source else "blocked",
        "Guest-only overlay and outside-tap dismissal are present in source; "
        "maximize/close remain disabled, and rotation/touch need device testing"
        if gesture_source else "Guest overlay with outside-tap dismissal is missing")
    add("apple_login_pairing_2fa","blocked",
        "Live iPhone SideStore/SideSign authentication and six-digit 2FA have not been reproduced on the rebuilt application")
    add("seven_day_refresh_and_install","blocked",
        "Policy code exists; free profile renewal requires Apple authentication, signing and verified same-bundle iPhone reinstall")
    add("real_device_visual_regression","blocked",
        "No paired iPhone run with portrait/landscape screenshots, touch hit tests and original Liquid Glass optics")
    add("signed_ipa_and_user_data","blocked",
        "No new four-bundle signed IPA, entitlement comparison, in-place installation, or verified data preservation")
    blockers=[x["id"] for x in checks if x["releaseRequired"] and x["status"]!="passed"]
    return {
        "schema":1,
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "project":"Scarlet Crystal clean rebuild",
        "figmaFileKey":manifest["source"]["fileKey"],
        "visualScreenCount":len(manifest["screens"]),
        "checks":checks,
        "releaseReady":not blockers,
        "blockingChecks":blockers,
        "simulatorEvidenceIsNotNativeGlass":True,
        "currentStatus":"BLOCKED" if blockers else "READY_FOR_DEVICE_RELEASE_REVIEW",
        "caveat":"Only a real signed app on the actual iPhone can establish native Liquid Glass and install correctness."
    }

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=ROOT/"rebuild/reports/live-readiness.json")
    p.add_argument("--enforce-release",action="store_true")
    a=p.parse_args()
    report=assess(ROOT)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("[SCARLET_READINESS]",report["currentStatus"])
    for x in report["checks"]:
        print(f"[{x['status']}] {x['id']}: {x['evidence']}")
    print("[REPORT]",a.output)
    return 2 if a.enforce_release and not report["releaseReady"] else 0

if __name__=="__main__":sys.exit(main())
