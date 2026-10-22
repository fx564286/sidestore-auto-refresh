"""Choose the smallest installed app/extension set for requested features.

This is NOT a method for synthesizing Apple entitlements, turning a guest IPA
into a system extension or bypassing iOS app isolation. Unknown capabilities
fail closed. Each required native extension has its own Apple App ID.
"""
import argparse
import json
from pathlib import Path
import plistlib
import zipfile

# Full native feature => required independently registered extension.
# Ordinary library APIs, hosted side loading and foreground App Intents reuse
# the containing application and incur zero new App IDs.
FEATURE_ROLES = {
    'guest_app_management': (),
    'independent_guest_process': ('LiveProcess',),
    'native_dynamic_island': ('LiveWidget',),
    'native_share_sheet_receiver': ('ShareExtension',),
    'app_shortcuts': (),
    'files_open_in': (),
    'sidestore_signing': (),
    'jit_orchestration': (),
    'custom_api_modules': (),
}
ROLE_ORDER = ('LiveProcess', 'LiveWidget', 'ShareExtension')
BASE = 'com.kdt.livecontainer'


def select(features: dict) -> dict:
    if not isinstance(features, dict) or not features:
        raise ValueError('No feature requirements supplied')
    unknown = set(features) - set(FEATURE_ROLES)
    if unknown:
        raise ValueError('Unmapped Apple API / extension requirements: ' + ', '.join(sorted(unknown)))
    if any(type(flag) is not bool for flag in features.values()):
        raise ValueError('Every feature flag must be a boolean')
    required = {role for feature, enabled in features.items() if enabled
                for role in FEATURE_ROLES[feature]}
    roles = ['host'] + [role for role in ROLE_ORDER if role in required]
    # Current code always builds a real LiveProcess and a real LiveWidget.
    # Fewer IDs may be conceptually possible under reduced feature requirements,
    # but require unimplemented bootstrap changes; do NOT report them buildable.
    build_supported = {'LiveProcess', 'LiveWidget'} <= required
    lost = [f for f, enabled in features.items() if not enabled]
    return {
        'schema': 1,
        'policy': 'feature_requirements_not_fixed_count',
        'features': features,
        'installable_roles': roles,
        'minimum_planned_app_ids': len(roles),
        'expected_unsigned_bundle_ids': [BASE] + [BASE + '.' + role for role in roles[1:]],
        'build_supported_by_current_v67_source': build_supported,
        'disabled_or_not_requested_features': lost,
        'limitations': (
            ['The 1- or 2-ID source refactor has NOT been implemented or tested.']
            if not build_supported else []
        ) + (
            ['Native share-sheet destination is unavailable; Open In/Files and user-installed Shortcuts are not identical.']
            if not features.get('native_share_sheet_receiver', False) else []
        ),
    }


def load_policy(path: Path) -> dict:
    policy = json.loads(path.read_text())
    if policy.get('selection_policy') != 'minimum_bundle_ids_without_unapproved_feature_loss':
        raise ValueError('Unreviewed minimization policy')
    return select(policy['features'])


def shell_environment(plan: dict) -> str:
    if not plan['build_supported_by_current_v67_source']:
        raise ValueError('Requested reduced layout requires an unimplemented guest/widget source redesign')
    required = set(plan['installable_roles'])
    # These flags adapt existing tested packaging paths. A widget and a
    # separate guest process remain required for this specific feature profile.
    return ('export NRG_V58_NATIVE_ISLAND=1\n'
            'export NRG_V66_4IDS=1\n'
            'export NRG_V67_3IDS=' + ('0' if 'ShareExtension' in required else '1') + '\n')


def verify_archive(path: Path, plan: dict) -> dict:
    """Check exact installable bundle set; nested non-installable frameworks ignored."""
    base = 'Payload/LiveContainer.app/'
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        host = plistlib.loads(archive.read(base + 'Info.plist'))
        if host['CFBundleIdentifier'] != BASE:
            raise ValueError('Unexpected unsigned host bundle ID')
        infos = [name for name in names if name.startswith(base + 'PlugIns/')
                 and name.endswith('.appex/Info.plist')]
        found = {plistlib.loads(archive.read(name))['CFBundleIdentifier'] for name in infos}
        required = set(plan['expected_unsigned_bundle_ids'][1:])
        if found != required or len(infos) != len(required):
            raise ValueError(f'IPA bundle mismatch: expected {sorted(required)} got {sorted(found)}')
        if plan['features'].get('native_dynamic_island') and host.get('NSSupportsLiveActivities') is not True:
            raise ValueError('Native Live Activities disabled in host')
        if plan['features'].get('files_open_in'):
            types = host.get('CFBundleDocumentTypes', [])
            if not any('public.item' in entry.get('LSItemContentTypes', []) for entry in types):
                raise ValueError('File Open In capability lost')
        if not plan['features'].get('native_share_sheet_receiver') and BASE + '.ShareExtension' in found:
            raise ValueError('Unrequested ShareExtension is installed')
    return {'archive': str(path), 'verified_app_ids': len(required) + 1,
            'roles': plan['installable_roles'], 'result': 'matched_required_roles',
            'device_signing_and_runtime': 'not_verified'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--required', type=Path, required=True)
    parser.add_argument('--write-plan', type=Path)
    parser.add_argument('--write-env', type=Path)
    parser.add_argument('--verify-ipa', type=Path)
    options = parser.parse_args()
    plan = load_policy(options.required)
    if options.write_env:
        options.write_env.parent.mkdir(parents=True, exist_ok=True)
        options.write_env.write_text(shell_environment(plan))
    if options.write_plan:
        options.write_plan.parent.mkdir(parents=True, exist_ok=True)
        options.write_plan.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    if options.verify_ipa:
        print(json.dumps(verify_archive(options.verify_ipa, plan), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({'minimum_planned_app_ids': plan['minimum_planned_app_ids'],
                          'roles': plan['installable_roles'],
                          'source_ready': plan['build_supported_by_current_v67_source']}))
