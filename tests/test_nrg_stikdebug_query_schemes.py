"""Exercise the actual GitHub Actions host-plist stamping code."""
from pathlib import Path
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/'.github/workflows/livecontainer-build.yml'
PLIST_REL='livecontainer-derived-data/Build/Products/Release-iphoneos/LiveContainer.app/Info.plist'


def stamp(host_info, sequence=214):
    data=WORKFLOW.read_text()
    m=re.search(r"python3 - <<'PY_NRG_V52'\n(.*?)\n          PY_NRG_V52",data,re.S)
    if not m:
        raise AssertionError('Missing host Info.plist stamp block')
    code='\n'.join(line[10:] for line in m.group(1).splitlines())+'\n'
    with tempfile.TemporaryDirectory() as tmp:
        info_path=Path(tmp)/PLIST_REL
        info_path.parent.mkdir(parents=True)
        info_path.write_bytes(plistlib.dumps(host_info))
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,
               env={**os.environ,'RUNNER_TEMP':tmp,'GITHUB_RUN_NUMBER':str(sequence)})
        after=plistlib.loads(info_path.read_bytes())
    return result,after


class StikDebugQueriesTests(unittest.TestCase):
    def test_preserves_host_identity_and_existing_queries(self):
        source={'CFBundleIdentifier':'com.kdt.livecontainer',
                'LSApplicationQueriesSchemes':['sidestore','livecontainer','livecontainer2','livecontainer3'],
                'UnrelatedValue':'kept'}
        result,after=stamp(source)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(after['CFBundleIdentifier'],'com.kdt.livecontainer')
        self.assertEqual(after['UnrelatedValue'],'kept')
        self.assertEqual(after['NRGOTASequence'],214)
        self.assertEqual(after['CFBundleVersion'],'3.8.192')
        self.assertEqual(after['CFBundleDisplayName'],'Scarlet Crystal')
        self.assertEqual(after['LSApplicationQueriesSchemes'],
                ['sidestore','livecontainer','livecontainer2','livecontainer3','stikdebug','stikjit'])

    def test_idempotence_no_duplicate_schemes(self):
        initial={'LSApplicationQueriesSchemes':['sidestore','stikdebug','stikjit']}
        first,p1=stamp(initial)
        second,p2=stamp(p1)
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(p1,p2)

    def test_rejects_broken_query_type_without_modifying_original(self):
        source={'LSApplicationQueriesSchemes':'stikdebug'}
        result,after=stamp(source)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(after,source)

    def test_packaged_ipa_verification_enforces_schemes(self):
        text=WORKFLOW.read_text()
        self.assertIn("assert set(('stikdebug', 'stikjit')).issubset(query_schemes)",text)
        self.assertIn("assert len(query_schemes)==len(set(query_schemes))",text)


if __name__=='__main__':
    unittest.main()
