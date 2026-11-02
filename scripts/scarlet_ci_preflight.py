#!/usr/bin/env python3
"""Scarlet CI fast fail-closed checks: catch YAML/version drift before Xcode.

Runs on an unmodified repository checkout in seconds. It doesn't skip the
release regression suite; that remains a separate required release profile.
"""
import argparse
from pathlib import Path
import re

WORKFLOW = ".github/workflows/livecontainer-build.yml"
PACKAGER = "scripts/package_livecontainer_combined.py"


class PreflightError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise PreflightError(reason)


def one(regex, text, label):
    hits = re.findall(regex, text)
    require(len(hits) == 1, f"{label}: expected exactly one, found {len(hits)}")
    return hits[0]


def verify(workflow: str, packager: str, root: Path) -> tuple[str, str]:
    version = one(r"info\['CFBundleVersion'\]\s*=\s*'(3\.8\.\d+)'", workflow,
                  "packaged CFBundleVersion")
    label = one(r"info\['ScarletBuildLabel'\]\s*=\s*'(V\d+)'", workflow,
                "packaged ScarletBuildLabel")
    require(
        f'info[\'ScarletBuildLabel\']=\'{label}\'' in workflow
        and f"main.get('CFBundleVersion')=='{version}'" in workflow
        and f"main.get('ScarletBuildLabel')=='{label}'" in workflow,
        "IPA packaging metadata/assertions drift"
    )
    require(
        f'p.write_text(t.replace("<string>3.8.209</string>","<string>{version}</string>",1)'
        in workflow,
        "Info.plist version stamping does not match packaging"
    )
    require(
        f'.replace("<string>V136</string>","<string>{label}</string>",1)' in workflow,
        "Info.plist label stamping does not match packaging"
    )
    require(
        f"grep -Fq '<string>{label}</string>' work/LiveContainer/LiveContainer/Info.plist"
        in workflow,
        "stale Info.plist label grep: fix the release gate before building"
    )
    require(
        f"grep -Fq '<string>{version}</string>' work/LiveContainer/LiveContainer/Info.plist"
        in workflow,
        "stale Info.plist version grep: fix the release gate before building"
    )
    require(
        f"if version == '{version}' and build_label != '{label}'" in packager,
        "packager version/label identity guard missing"
    )
    require(
        f"Scarlet-Crystal-{label}-UNSIGNED.ipa" in workflow,
        "final IPA filename disagrees with build label"
    )

    old_checks = re.findall(
        r"grep -Fq '<string>(V\d+)</string>' work/LiveContainer/LiveContainer/Info\.plist",
        workflow
    )
    require(old_checks and old_checks[-1] == label,
            f"last Info.plist grep is stale: {old_checks[-1:]}, expected {label}")

    # The source owner's invariant requires all three actions and exactly
    # one existing host picker; this test must remain a compile-stage gate.
    require("test_v149_controls.py -v" in workflow, "focused V149 generated UI QA missing")
    require("patch_v149_controls.py work/LiveContainer" in workflow,
            "V149 patch missing")
    require("swiftc -frontend -parse work/LiveContainer/MultitaskSupport/MultitaskDockView.swift"
            in workflow, "Swift dock parser gate missing")
    require((root / "tests" / "test_v149_controls.py").is_file(),
            "V149 focused test script missing")
    if label in ('V169', 'V170', 'V171', 'V172', 'V173', 'V174', 'V175'):
        for required in (
            'patch_v169_event_geometry_transport.py work/LiveContainer layout',
            'patch_v169_event_geometry_transport.py work/EmbeddedSideStore pairing',
            'test_v169_geometry_transport.py -v',
            'SCARLET_V169_EVENT_DRIVEN_VIEWPORT',
            'SCARLET_V169_DEFERRED_ROTATION_RETIRED',
            'SCARLET_V169_NO_VPN_PEER_FALLBACK',
            'patch_v169_event_geometry_transport.py "$MUX" tunnel',
            'SCARLET_V169_DUALSTACK_TUNNEL_DISCOVERY',
            'patch_v167_restore_ondevice_pairing.py work/LiveContainer work/EmbeddedSideStore',
            'patch_v164_rp_handshake_recovery.py work/EmbeddedSideStore',
        ):
            require(required in workflow, 'V169 core patch gate missing: ' + required)
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V169 native top-tab marker gate missing')
        require((root/'scripts'/'patch_v169_event_geometry_transport.py').is_file(),
                'V169 geometry/transport patch missing')
        require((root/'tests'/'test_v169_geometry_transport.py').is_file(),
                'V169 regression tests missing')
    if label == 'V170' and version == '3.8.244':
        for required in ('patch_v170_rp_reset_failure.py work/EmbeddedSideStore',
                         'patch_v170_landscape_only.py work/LiveContainer',
                         'test_v170_landscape_only.py -v',
                         'SCARLET_V170_LANDSCAPE_ONLY',
                         'patch_v170_pairing_ui_context.py work/LiveContainer',
                         'test_v170_rp_reset_failure.py -v',
                         'test_v170_pairing_ui_context.py -v',
                         'SCARLET_V170_PAIR_COMMAND_CONTEXT'):
            require(required in workflow, 'V170 refresh diagnostics gate missing: ' + required)
    if label == 'V171' and version == '3.8.245':
        for required in ('patch_v170_rp_reset_failure.py work/EmbeddedSideStore',
                         'patch_v170_landscape_only.py work/LiveContainer',
                         'patch_v171_landscape_scene_frame.py work/LiveContainer',
                         'patch_v171_rp_refresh_xpc.py work/LiveContainer',
                         'test_v171_landscape_scene_frame.py -v',
                         'test_v171_rp_refresh_xpc.py -v',
                         'SCARLET_V171_LANDSCAPE_SCENE_FRAME',
                         'SCARLET_V171_RP_FAILURE_XPC'):
            require(required in workflow, 'V171 unified patch gate missing: ' + required)
        for required in ('patch_v171_landscape_scene_frame.py', 'patch_v171_rp_refresh_xpc.py'):
            require((root/'scripts'/required).is_file(), 'V171 patch missing: '+required)
    if label == 'V172' and version == '3.8.246':
        for required in ('patch_v170_landscape_only.py work/LiveContainer',
                         'patch_v171_landscape_scene_frame.py work/LiveContainer',
                         'patch_v172_scene_restore.py work/LiveContainer',
                         'patch_v172_media_evidence.py work/LiveContainer',
                         'test_v172_scene_restore.py -v',
                         'test_v172_media_evidence.py -v',
                         'SCARLET_V172_RESTORE_PORTRAIT',
                         'SCARLET_V172_MEDIA_EVIDENCE'):
            require(required in workflow, 'V172 unified source/test gate missing: ' + required)
        for required in ('patch_v172_scene_restore.py', 'patch_v172_media_evidence.py'):
            require((root/'scripts'/required).is_file(), 'V172 source missing: ' + required)
    if label == 'V173' and version == '3.8.247':
        for required in ('patch_v173_single_scene_owner.py work/LiveContainer',
                         'test_v173_single_scene_owner.py -v',
                         'SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER'):
            require(required in workflow, 'V173 single owner build gate missing: ' + required)
        require((root/'scripts'/'patch_v173_single_scene_owner.py').is_file(),
                'V173 geometry patch missing')
        require((root/'tests'/'test_v173_single_scene_owner.py').is_file(),
                'V173 geometry regression test missing')
    if label == 'V174' and version == '3.8.248':
        for required in ('patch_v174_guest_render.py work/LiveContainer',
                         'test_v174_guest_render.py -v',
                         'SCARLET_V174_RENDER_SURFACE',
                         'SCARLET_V174_BOUNDED_GEOMETRY'):
            require(required in workflow, 'V174 render and scene gate missing: '+required)
        for rel in ('scripts/patch_v174_guest_render.py',
                    'tests/test_v174_guest_render.py',
                    'reports/V174_REVIEW_PLAN.md'):
            require((root/rel).is_file(), 'V174 source/review missing: '+rel)
    if label == 'V175' and version == '3.8.249':
        for required in ('patch_v175_layout_media.py work/LiveContainer',
                         'test_v175_layout_media.py -v',
                         'SCARLET_V175_LAYOUT_BEFORE_GUEST_COMMIT',
                         'SCARLET_V175_SYMMETRIC_MEDIA_GEOMETRY'):
            require(required in workflow, 'V175 geometry/media gate missing: '+required)
        for rel in ('scripts/patch_v175_layout_media.py', 'tests/test_v175_layout_media.py'):
            require((root/rel).is_file(), 'V175 required patch/test missing: '+rel)
    if label == 'V167':
        for required in ('patch_v167_restore_ondevice_pairing.py work/LiveContainer work/EmbeddedSideStore',
                         'test_v167_ondevice_restore.py -v',
                         'SCARLET_V167_ONDEVICE_HOST', 'SCARLET_V167_ONDEVICE_UI',
                         'SCARLET_V167_ATOMIC_PAIRING_PRESERVE',
                         'SCARLET_V167_PIN_LOG_REDACTION',
                         'wirelessPairing.start(outPath: out.path)',
                         'patch_v166_integrated_rp.py work/LiveContainer',
                         'patch_v164_rp_handshake_recovery.py work/EmbeddedSideStore'):
            require(required in workflow,'V167 native pairing restoration gate missing: '+required)
        require((root/'scripts'/'patch_v167_restore_ondevice_pairing.py').is_file(),
                'V167 original pairing backend adapter missing')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V167 native top-tab marker gate missing')
    if label == 'V166':
        for required in ('patch_v166_integrated_rp.py work/LiveContainer',
                         'test_v166_integrated_rp.py -v',
                         'test_v166_package_parity.py -v',
                         'SCARLET_V166_AUTOMATIC_RP_HANDOFF',
                         'SCARLET_V166_AUTO_IMPORT_ONCE',
                         'patch_v165_first_install_flow.py work/LiveContainer',
                         'patch_v164_rp_handshake_recovery.py work/EmbeddedSideStore'):
            require(required in workflow,'V166 integrated setup gate missing: '+required)
        for part in ('installer/scarlet_oneclick.py', 'installer/install_integration.py',
                     'tests/test_integrated_setup.py', 'scripts/patch_v166_integrated_rp.py'):
            require((root/part).is_file(),'V166 integrated installer missing: '+part)
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V166 native top-tab marker gate missing')
    if label == 'V165':
        for required in ('patch_v165_first_install_flow.py work/LiveContainer',
                         'test_v165_first_install_flow.py -v',
                         'test_v165_package_parity.py -v',
                         'SCARLET_V165_INBOX_REUSE',
                         'SCARLET_V165_SINGLE_NEXT_ACTION',
                         'SCARLET_V165_FIRST_INSTALL',
                         'patch_v164_rp_handshake_recovery.py work/EmbeddedSideStore',
                         'patch_v163_button_size_native.py work/LiveContainer'):
            require(required in workflow, 'V165 setup/unchanged transport gate missing: '+required)
        require((root/'scripts'/'patch_v165_first_install_flow.py').is_file(),
                'V165 first-install patch source missing')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V165 native top-tab marker gate missing')
    if label == 'V164':
        for required in ('patch_v164_rp_handshake_recovery.py work/EmbeddedSideStore',
                         'test_v164_rp_handshake_recovery.py -v',
                         'verify_v164_embedded_rp.py artifacts/LiveContainer-SideStore-v3.0.3-rc.ipa',
                         'SCARLET_V164_TRANSPORT_RESYNC',
                         'SCARLET_V142_NETWORK_GENERATION_GUARD',
                         'patch_v163_button_size_native.py work/LiveContainer'):
            require(required in workflow, 'V164 RP transport/unchanged UI gate missing: '+required)
        require((root/'scripts'/'patch_v164_rp_handshake_recovery.py').is_file(),
                'V164 bounded RP repair source missing')
        require((root/'scripts'/'verify_v164_embedded_rp.py').is_file(),
                'V164 embedded SideStore verifier missing')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V164 native top-tab marker gate missing')
    if label == 'V163':
        for required in ('patch_v163_button_size_native.py work/LiveContainer',
                         'test_v163_button_size_native.py -v',
                         'test_v163_package_parity.py -v',
                         'V163_V162_BASELINE_DOCK=',
                         'SCARLET_V163_BUTTON_FOOTPRINT',
                         'SCARLET_V163_PRESS_CLEARANCE'):
            require(required in workflow, 'V163 size/long-press regression gate missing: '+required)
        require((root / 'scripts' / 'patch_v163_button_size_native.py').is_file(),
                'V163 native button patch missing')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V163 native top-tab marker gate missing')
    if label == 'V162':
        for required in ('patch_v162_panel_scale.py work/LiveContainer',
                         'test_v162_panel_scale.py -v',
                         'test_v162_package_parity.py -v',
                         'SCARLET_V162_SIXTH_SMALLER',
                         'SCARLET_V162_HIDE_REDUNDANT_FOOTER'):
            require(required in workflow, 'V162 size gate missing: ' + required)
        require((root / 'scripts' / 'patch_v162_panel_scale.py').is_file(),
                'V162 panel patch missing')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V162 native top-tab marker gate missing')
    if label == 'V161':
        for required in ('patch_v161_compact_outside.py work/LiveContainer',
                         'test_v161_compact_outside.py -v',
                         'test_v161_package_parity.py -v',
                         'SCARLET_V161_BLANK_PANEL_DISMISS',
                         'SCARLET_V161_RESIZE_TAB'):
            require(required in workflow, 'V161 compact panel/outside gate missing: '+required)
        require((root / 'scripts' / 'patch_v161_compact_outside.py').is_file(),
                'V161 missing patch source')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V161 native top-tab marker gate missing')
    if label == 'V160':
        for required in ('patch_v160_outside_visual_parity.py work/LiveContainer',
                         'test_v160_outside_visual_parity.py -v',
                         'test_v160_package_parity.py -v',
                         'SCARLET_V160_OUTSIDE_RETURN',
                         'SCARLET_V160_GEOMETRY_PARITY',
                         'SCARLET_V160_GLASS_CONTRAST'):
            require(required in workflow, 'V160 outside/glass/geometry gate missing: ' + required)
        require((root / 'scripts' / 'patch_v160_outside_visual_parity.py').is_file(),
                'V160 source patch missing')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                'V160 native top-tab marker gate missing')
    if label == 'V159':
        for required in ('patch_v159_panel_height_native_action.py work/LiveContainer',
                         'test_v159_panel_action_press.py -v',
                         'test_v159_package_parity.py -v',
                         'SCARLET_V159_PINNED_OUTER_FRAME',
                         'SCARLET_V159_ACTION_NATIVE_PRESS'):
            require(required in workflow,
                    'V159 panel frame/native action CI gate missing: '+required)
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                "V159 native top-tab marker gate missing")
    if label == 'V158':
        for required in ('patch_v158_unified_action_glass.py work/LiveContainer',
                         'test_v158_unified_action_glass.py -v',
                         'test_v158_package_parity.py -v',
                         'SCARLET_V158_EQUAL_TAB_FRAME',
                         'SCARLET_V158_ACTION_UNCLIPPED'):
            require(required in workflow,
                    'V158 stable panel and action optical glass gate missing: '+required)
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                "V158 surviving native top-tab UI marker gate missing")
    if label == 'V157':
        for required in ('patch_v157_panel_width.py work/LiveContainer',
                         'test_v157_wide_panel.py -v',
                         'test_v157_package_parity.py -v',
                         'SCARLET_V157_WIDE_PANEL'):
            require(required in workflow,
                    'V157 wider native glass panel CI gate missing: '+required)
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                "V157 surviving native top-tab UI marker gate missing")
    if label == 'V156':
        for required in ('patch_v156_panel_size_outside.py work/LiveContainer',
                         'test_v156_stable_glass.py -v',
                         'test_v156_package_parity.py -v',
                         'SCARLET_V156_STABLE_PANEL_HEIGHT'):
            require(required in workflow, 'V156 stable-panel gate missing: '+required)
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                "V156 surviving native top-tab UI marker gate missing")
    if label == 'V155':
        require('patch_v155_single_liveprocess.py work/LiveContainer' in workflow,
                'V155 single-path source elimination not applied')
        require('test_v155_single_liveprocess.py -v' in workflow,
                'V155 one-mode + recent/outside regressions missing')
        require("grep -Fq 'SCARLET_V151_TAB_NATIVE_PRESS' "
                "work/LiveContainer/MultitaskSupport/MultitaskDockView.swift" in workflow,
                "V155 surviving native top-tab UI marker gate missing")
        for stale in ("grep -Fq 'SCARLET_V128_DIRECT_SCENE_RECOVERY'",
                      "grep -Fq 'SCARLET_V114_DIRECT_PICKER_REPAIR'",
                      "grep -Fq 'SCARLET_V114_PICKER_TABS'",
                      "grep -Fq 'SCUnifiedGuestUIBridge'"):
            require(stale not in workflow,
                    'V155 release still demands deleted Direct source: '+stale)
        require('audit_v107_active_guest_ui.py work/LiveContainer' in workflow
                and 'audit_v102_final_source.py work/LiveContainer' in workflow,
                'V155 source ownership audit missing')

    if label == 'V154':
        require('patch_v154_three_runtime_fixes.py work/LiveContainer' in workflow,
                'V154 runtime source patch not applied')
        require('test_v154_runtime_three_fixes.py -v' in workflow,
                'V154 recent/outside/Direct source regression missing')
    if label == 'V153':
        require('patch_v153_three_fixes.py work/LiveContainer' in workflow,
                'V153 three-fix source patch missing from release')
        require('test_v153_three_fixes.py -v' in workflow,
                'V153 three-fix regression missing from release')
        require('test_v153_package_parity.py -v' in workflow,
                'V153 binary marker parity missing from release')
    if label == 'V152':
        require('V152_PATCHED_LIVECONTAINER=work/LiveContainer' in workflow,
                'V152 all-guest postpatch source audit must run')
        require('test_v152_universal_guest_parity.py -v' in workflow,
                'V152 universal geometry regression gate missing')
        require('test_v58_fullscreen_activity.py -v' in workflow,
                'V152 historical V58 fullscreen regression gate missing')
    if label == 'V151':
        for script in ('patch_v151_glass_polish.py', 'patch_v151_geometry.py'):
            require(f'{script} work/LiveContainer' in workflow,
                    f'V151 missing applied source patch {script}')
        for test in ('test_v151_glass_polish.py', 'test_v151_geometry.py',
                     'test_v151_package_parity.py'):
            require(f'{test} -v' in workflow, f'V151 regression gate missing {test}')
    if label == 'V150':
        require('patch_v150_touch_glass.py work/LiveContainer' in workflow,
                'V150 source patch missing from release flow')
        require('test_v150_touch_glass.py -v' in workflow and
                'test_v150_package_parity.py -v' in workflow,
                'V150 real glass/outside/source and binary checks missing')


    # Accuracy: release cannot become fast mode automatically on other
    # branches; release retains full historical skip-allowlist suite.
    require("SCARLET_CI_PROFILE:" in workflow and "'release'" in workflow,
            "CI profile must default to release")
    require("name: Run repository checks before patches" in workflow,
            "release full suite must remain present")
    require("run_required_tests.py" in workflow
            and "required_test_skip_allowlist.json" in workflow,
            "release full suite and skip accounting must be retained")
    require("name: Fast focused checks before patches" in workflow,
            "fast smoke suite required")
    require("name: V78 Gate 1 unsigned archive and Mach-O verification" in workflow,
            "Mach-O archive verification must remain on both profiles")
    require("CODE_SIGNING_ALLOWED=NO" in workflow,
            "unsigned IPA signing contract changed")
    require("concurrency:" in workflow and "github.ref" in workflow,
            "separate-branch concurrency isolation missing")
    print(f"SCARLET_CI_FAST_PREFLIGHT=PASS version={version} label={label}"
          " profiles=fast,release archive_gate=present")
    return version, label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    a = parser.parse_args()
    verify((a.root / WORKFLOW).read_text(),
           (a.root / PACKAGER).read_text(), a.root)


if __name__ == "__main__":
    main()
