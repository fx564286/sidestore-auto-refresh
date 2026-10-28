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
    if label == 'V155':
        require('patch_v155_single_liveprocess.py work/LiveContainer' in workflow,
                'V155 single-path source elimination not applied')
        require('test_v155_single_liveprocess.py -v' in workflow,
                'V155 one-mode + recent/outside regressions missing')
        for stale in ("grep -Fq 'SCARLET_V128_DIRECT_SCENE_RECOVERY'",
                      "grep -Fq 'SCARLET_V114_DIRECT_PICKER_REPAIR'",
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
