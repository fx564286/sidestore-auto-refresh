"""Constrain the V67 candidate to three installable App IDs.

The existing LiveContainer main app already exposes public.item via
CFBundleDocumentTypes and receives Files/Open In URLs. No new extension is
needed for those iOS document routes. This does *not* preserve an iOS share
sheet target; Apple's share extension point requires a separate extension.
"""
import os
from pathlib import Path

EXPECTED_EXTENSIONS = frozenset({'LiveProcess', 'LiveWidget'})


def preflight(host_path: Path) -> None:
    import plistlib
    info = plistlib.loads((host_path / 'Info.plist').read_bytes())
    document_types = info.get('CFBundleDocumentTypes', [])
    if not any('public.item' in entry.get('LSItemContentTypes', [])
               for entry in document_types):
        raise ValueError('V67 requires an existing Files/Open In document route')
    if info.get('LSSupportsOpeningDocumentsInPlace') is not True:
        raise ValueError('V67 must retain documents-in-place')


def patch_workflow_environment() -> dict[str, str]:
    return {'NRG_V58_NATIVE_ISLAND': '1',
            'NRG_V66_4IDS': '1',
            'NRG_V67_3IDS': '1'}


def assert_invariants() -> None:
    if os.environ.get('NRG_V67_3IDS') == '1':
        if os.environ.get('NRG_V66_4IDS') != '1':
            raise ValueError('V67 requires the V66 main-app AppIntent migration')
        if os.environ.get('NRG_V58_NATIVE_ISLAND') != '1':
            raise ValueError('V67 must retain the real Dynamic Island extension')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    preflight(args.check)
