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

    print("[SCARLET_V180] full source-preserving visual patch chain applied")



if __name__ == "__main__":
    main()
