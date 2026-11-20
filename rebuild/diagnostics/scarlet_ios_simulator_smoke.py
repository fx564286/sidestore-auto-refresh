#!/usr/bin/env python3
"""Run an actual, isolated iPhone Simulator smoke attempt for integrated Scarlet.

The installed iPhoneOS archive is NEVER passed to simctl: this probe builds a
separate iphonesimulator variant and records the exact failing stage if blocked.
No Apple account, signing secrets, device pairing or real user data are used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time


def select_iphone(inventory: dict) -> dict | None:
    candidates = []
    for runtime, entries in inventory.get('devices', {}).items():
        match = re.search(r'SimRuntime\.iOS-(\d+)(?:-(\d+))?', runtime)
        if not match:
            continue
        version = (int(match.group(1)), int(match.group(2) or 0))
        for device in entries:
            if (isinstance(device, dict) and
                    device.get('name', '').startswith('iPhone ') and
                    device.get('udid') and device.get('isAvailable', True)):
                candidates.append((version, device))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (
        item[0][0], item[0][1],
        1 if item[1].get('state') == 'Booted' else 0,
        1 if 'Pro' in item[1]['name'] else 0), reverse=True)
    return candidates[0][1]


class SmokeBlocked(Exception):
    def __init__(self, stage: str, reason: str):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def run(args: list[str], *, stage: str, timeout: int = 100,
        cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError) as error:
        raise SmokeBlocked(stage, f'command_unavailable_or_timeout:{type(error).__name__}') from error
    if result.returncode:
        safe = (result.stderr or result.stdout or '')[-850:].strip()
        raise SmokeBlocked(stage, f'exit_{result.returncode}:{safe}')
    return result.stdout.strip()


def simulator_build(engine: Path, products: Path, report_dir: Path) -> Path:
    project = engine / 'LiveContainer.xcodeproj'
    if not project.is_dir():
        raise SmokeBlocked('simulator_source_missing', 'integrated_project_not_found')
    command = [
        'xcodebuild', 'build', '-project', str(project), '-scheme', 'LiveContainer',
        '-configuration', 'Release', '-sdk', 'iphonesimulator',
        '-destination', 'generic/platform=iOS Simulator',
        '-derivedDataPath', str(products), '-jobs', '2',
        'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO',
        'COMPILER_INDEX_STORE_ENABLE=NO',
    ]
    log = report_dir / 'simulator-xcodebuild.log'
    with log.open('w', encoding='utf-8') as f:
        try:
            result = subprocess.run(command, stdout=f, stderr=subprocess.STDOUT,
                                    text=True, timeout=1100, check=False)
        except (subprocess.TimeoutExpired, OSError) as error:
            raise SmokeBlocked('simulator_build_failed', f'build_timeout_or_spawn:{type(error).__name__}') from error
    if result.returncode:
        errors = [line.strip()[:400] for line in log.read_text(errors='replace').splitlines()
                  if any(marker in line for marker in ('error:', 'fatal error:', 'BUILD FAILED',
                                                       'linker command failed'))]
        raise SmokeBlocked('simulator_build_failed',
                           f'exit_{result.returncode}:' + ' | '.join(errors[:8]))
    app = products / 'Build/Products/Release-iphonesimulator/LiveContainer.app'
    if not (app / 'Info.plist').is_file():
        raise SmokeBlocked('simulator_build_failed', 'simulator_app_missing_after_build')
    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=Path, default=Path('engine/LiveContainer'))
    parser.add_argument('--report-dir', type=Path, default=Path('report/ios-simulator'))
    args = parser.parse_args()
    dest = args.report_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    report = {
        'schema': 1, 'kind': 'real_iphonesimulator_compile_install_launch_screenshot',
        'result': 'not_attempted', 'stage': 'initialization',
        'runtime_name': None, 'device_udid_tail': None,
        'app_bundle_id': None,
        'limitations': 'Simulator cannot prove Apple portal issuance, RSD pairing, real device install, or JIT-less kernel behavior.',
    }
    udid = None
    started_here = False
    try:
        available = run(['xcrun', 'simctl', 'list', '-j', 'devices', 'available'],
                        stage='simulator_runtime_unavailable')
        chosen = select_iphone(json.loads(available))
        if chosen is None:
            raise SmokeBlocked('simulator_runtime_unavailable', 'no_available_iphone_runtime')
        udid = chosen['udid']
        report['runtime_name'] = chosen['name']
        report['device_udid_tail'] = udid[-6:]
        report['stage'] = 'simulator_boot'
        if chosen.get('state') != 'Booted':
            run(['xcrun', 'simctl', 'boot', udid], stage='simulator_boot_failed', timeout=130)
            started_here = True
        run(['xcrun', 'simctl', 'bootstatus', udid, '-b'], stage='simulator_boot_failed',
            timeout=260)
        report['stage'] = 'simulator_build'
        derived = Path(os.environ.get('RUNNER_TEMP', '/tmp')).resolve() / 'ScarletSimDerivedData'
        app = simulator_build(args.engine.resolve(), derived, dest)
        report['stage'] = 'simulator_install'
        with (app / 'Info.plist').open('rb') as f:
            bundle_id = plistlib.load(f).get('CFBundleIdentifier')
        if not isinstance(bundle_id, str) or not bundle_id:
            raise SmokeBlocked('simulator_install_failed', 'built_app_bundle_id_missing')
        report['app_bundle_id'] = bundle_id
        run(['xcrun', 'simctl', 'install', udid, str(app)],
            stage='simulator_install_failed', timeout=200)
        report['stage'] = 'simulator_launch'
        launch_receipt = run(['xcrun', 'simctl', 'launch', '--terminate-running-process',
                              udid, bundle_id], stage='simulator_launch_failed', timeout=100)
        report['launch_receipt'] = launch_receipt[:220]
        time.sleep(8)
        report['stage'] = 'simulator_screenshot'
        screenshot = dest / 'iphone-simulator-after-launch.png'
        run(['xcrun', 'simctl', 'io', udid, 'screenshot', str(screenshot)],
            stage='simulator_screenshot_failed', timeout=95)
        if screenshot.stat().st_size < 1024:
            raise SmokeBlocked('simulator_screenshot_failed', 'screenshot_empty')
        report['screenshot_bytes'] = screenshot.stat().st_size
        report['result'] = 'simulator_launch_screenshot_captured'
        report['stage'] = 'complete'
        print('[SIMULATOR-PASS] Real iPhone Simulator app install, launch and screenshot captured; UI correctness not asserted.')
        return 0
    except (SmokeBlocked, json.JSONDecodeError) as error:
        report['result'] = 'blocked'
        report['stage'] = error.stage if isinstance(error, SmokeBlocked) else 'simulator_runtime_unavailable'
        report['reason'] = (error.reason if isinstance(error, SmokeBlocked)
                            else 'simctl_inventory_json_invalid')[:1400]
        print('[SIMULATOR-BLOCKED] ' + report['stage'] + ': ' + report['reason'][:650],
              file=sys.stderr)
        return 2
    finally:
        if started_here and udid:
            try:
                run(['xcrun', 'simctl', 'shutdown', udid],
                    stage='simulator_shutdown_unavailable', timeout=50)
            except SmokeBlocked:
                report['cleanup'] = 'shutdown_failed'
        (dest / 'smoke.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
