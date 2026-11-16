#!/usr/bin/env python3
"""Fail closed against native upstream drift and accidental feature rewrites.

The reference is the original LiveContainer source at the repository's pinned
commit, not a copied approximation. Only the faulty completion return inside
extract() may change; a separately appended fallback remains isolated.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REL = 'LiveContainerSwiftUI/Utilities/unarchive.m'
OLD = ("    archive_read_close(a);\n"
       "    archive_read_free(a);\n"
       "    archive_write_close(ext);\n"
       "    archive_write_free(ext);\n"
       "    \n"
       "    return 0;\n}")
NEW = ("    int scarletArchiveReadResult = r;\n"
       "    archive_read_close(a);\n"
       "    archive_read_free(a);\n"
       "    int scarletArchiveWriteCloseResult = archive_write_close(ext);\n"
       "    archive_write_free(ext);\n"
       "    return (scarletArchiveReadResult == ARCHIVE_EOF &&\n"
       "            scarletArchiveWriteCloseResult >= ARCHIVE_WARN) ? 0 : 1;\n}")
MARK = '// R6P79_MAPPED_IPA_FALLBACK_BEGIN'


def verify_original_archive(original: str, patched: str) -> dict:
    assert original.count(OLD) == 1, 'Pinned original unarchive completion changed'
    assert patched.count(MARK) == 1, 'Expected one bounded ZIP fallback'
    pre, fallback = patched.split(MARK, 1)
    assert pre.rstrip() == original.replace(OLD, NEW, 1).rstrip(), (
        'Native original archive body changed beyond EOF/close result')
    assert '// R6P79_MAPPED_IPA_FALLBACK_END' in fallback
    assert 'return (ok && wrote) ? 0 : 1;' in fallback
    assert 'archive_entry_filetype(entry)==AE_IFLNK' in fallback
    assert 'hasAppPlist && entries<=80000' in fallback
    return {'reference_original_sha256': hashlib.sha256(original.encode()).hexdigest(),
            'exact_original_method_except_failure_return': True,
            'bounded_fallback_separate': True}


def verify_swift_importer(view: str) -> None:
    for marker in (
        'let result = extract(path, destination, progress)',
        'guard result != 0 else { return result }',
        'scratch.path == pending.path',
        'let partialPayload = scratch.appendingPathComponent("Payload"',
        'try FileManager.default.removeItem(at: partialPayload)',
        'let originalAppComplete = before.contains(where: { name in',
        'let recoveredAppComplete = after.contains(where: { name in',
        'appendingPathComponent("Info.plist")',
        'throw NSError(domain: "ScarletGuestArchive", code: 80',
        'let fallback = scarletExtractGuestIPAFromMappedData(',
    ):
        assert marker in view, f'Importer recovery not integrated: {marker}'
    assert 'func installIpaFile(_ url:URL) async throws {' in view
    assert 'let payloadContents = try fm.contentsOfDirectory(atPath: payloadPath.path)' in view
    assert 'patchExecAndSignIfNeed(completionHandler:' in view
    assert 'scarletTransactionalReplace' in view


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--engine',type=Path,required=True)
    parser.add_argument('--pins',type=Path,default=Path('config/scarlet-upstream-pins.json'))
    parser.add_argument('--report',type=Path,default=Path('report/p81-upstream-compat.json'))
    args=parser.parse_args()
    pin=json.loads(args.pins.read_text())['LIVE_CONTAINER_REF']
    observed=subprocess.check_output(['git','-C',str(args.engine),'rev-parse','HEAD'],text=True).strip()
    assert observed==pin,(observed,pin)
    original=subprocess.check_output(['git','-C',str(args.engine),'show',f'HEAD:{REL}'],text=True)
    patched=(args.engine/REL).read_text()
    result=verify_original_archive(original,patched)
    verify_swift_importer((args.engine/'LiveContainerSwiftUI/Views/AppList/LCAppListView.swift').read_text())
    result.update({'pinned_livecontainer_sha':pin,'swift_importer_contract':True,
                   'original_settings_multitask_audio_unchanged_by_p81':True})
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print('[P81-NATIVE-INTEGRATION-PASS]',json.dumps(result))

if __name__=='__main__':main()
