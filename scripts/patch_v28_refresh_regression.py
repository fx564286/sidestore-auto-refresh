#!/usr/bin/env python3
"""Restore V26 provisioning behavior for existing-app refresh; retain V27 installs."""
from pathlib import Path
import sys

PATH = 'SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift'
MARKER = 'NRG_V28_RESTORE_V26_REFRESH'


def patch(root: Path):
    path = root / PATH
    s = path.read_text(encoding='utf-8')
    if MARKER in s:
        assert s.count(MARKER) == 2, 'partial V28 patch'
        return
    if 'NRG_V27_PROFILE_CAPACITY_PREFLIGHT' not in s or 'NRG_V27_FREE_TEAM_SERIAL_PROVISIONING' not in s:
        raise ValueError('Missing V27 anchor')
    a = '        if team.type == .free {\n            let ordered = targetAppBundle.appExtensions.sorted'
    b = '        // NRG_V28_RESTORE_V26_REFRESH: keep V26 parallel profile renewal for installed apps.\n        if team.type == .free && self.context.installedApp == nil {\n            let ordered = targetAppBundle.appExtensions.sorted'
    if s.count(a) != 1:
        raise ValueError('V27 free team anchor mismatch')
    s = s.replace(a, b, 1)
    a = '        guard team.type == .free else { return }\n        let existing: [ALTAppID]'
    b = '        // NRG_V28_RESTORE_V26_REFRESH: V27 App ID budget is for new installs only.\n        guard team.type == .free && self.context.installedApp == nil else { return }\n        let existing: [ALTAppID]'
    if s.count(a) != 1:
        raise ValueError('V27 preflight anchor mismatch')
    s = s.replace(a, b, 1)
    assert s.count(MARKER) == 2
    path.write_text(s, encoding='utf-8')
    print('[PASS] Existing-app refresh uses V26 profile path; V27 new install preserved')

if __name__ == '__main__':
    if len(sys.argv) != 2: raise SystemExit('usage: patch_v28_refresh_regression.py <EmbeddedSideStore>')
    patch(Path(sys.argv[1]))
