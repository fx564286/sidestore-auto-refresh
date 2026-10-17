"""V33 increased-memory capability on a free Apple Personal Team.

Test the actual pinned SideSign code, not a mock of the core transform. All
checks are static/offline; CI does not contact the Apple Developer portal.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
PIN="a731c0d5a9a6617c7b385ae493e07ffb7f81cd5d"
SOURCE=Path(os.environ.get("SIDESIGN_TEST_SOURCE", ROOT/"work/EmbeddedSideStore/Dependencies/SideSign"))
FILE=ROOT/"scripts/patch_v33_memory_capability.py"
spec=importlib.util.spec_from_file_location("v33_capability",FILE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class V33MemoryCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original={}
        for relative in mod.FILES:
            cls.original[relative]=subprocess.check_output(
                ["git","-C",str(SOURCE),"show",f"{PIN}:{relative}"],text=True)
        cls.new=mod.transform(cls.original)

    def test_exact_pinned_transform_and_idempotency(self):
        self.assertNotEqual(self.original,self.new)
        self.assertEqual(mod.transform(self.new),self.new)
        self.assertEqual(set(self.new),set(mod.FILES))
        for file in mod.FILES:
            self.assertEqual(self.new[file].count(mod.MARKER),1)

    def test_free_personal_team_and_no_paid_capabilities(self):
        s=self.new[mod.FILES[0]]
        a=s.index("static let freeFeatures")
        b=s.index("static let paidFeatures",a)
        f=s[a:b]
        self.assertIn(".increasedMemoryLimit",f)
        self.assertNotIn(".extendedVirtualAddressing",f)
        self.assertNotIn(".increasedDebuggingMemoryLimit",f)
        self.assertIn('self == .increasedMemoryLimit ? "INCREASED_MEMORY_LIMIT" : nil',s)

    def test_apple_v1_patch_with_same_app_id_and_team(self):
        a=self.new[mod.FILES[1]]
        self.assertIn("func enableCapabilities(",a)
        self.assertIn('"bundleIdCapabilities"',a)
        self.assertIn('"type": "bundleIds"',a)
        self.assertIn('"type": "capabilities"',a)
        self.assertIn('"id": appID.identifier',a)
        self.assertIn('"teamId": team.identifier',a)
        self.assertIn('request.httpMethod = "PATCH"',a)
        self.assertIn('String: Any',a)
        self.assertIn('try await enableCapabilities(capabilities.sorted()',a)
        self.assertNotIn('try? await enableCapabilities',a)
        self.assertIn('capabilityIDs.allSatisfy({ $0 == "INCREASED_MEMORY_LIMIT" })',a)

    def test_custom_services_json_patch_preserves_auth_flow(self):
        s=self.new[mod.FILES[2]]
        self.assertIn('request.setValue($1, forHTTPHeaderField: $0)',s)
        self.assertIn('let (data, response) = try await session.data(for: request)',s)
        self.assertIn('guard (200..<300).contains(status)',s)
        self.assertIn('X-Apple-GS-Token',s)
        self.assertIn('X-Apple-I-MD-M',s)
        self.assertIn('X-MMe-Client-Info',s)
        self.assertIn('"[redacted capability response]"',s)
        self.assertNotIn('print(apiSession',s)

    def test_partial_patch_and_upstream_changes_rejected(self):
        partial=dict(self.new)
        partial[mod.FILES[0]]=self.original[mod.FILES[0]]
        with self.assertRaises(ValueError):
            mod.transform(partial)
        changed=dict(self.original)
        changed[mod.FILES[0]]=changed[mod.FILES[0]].replace(
            "static let freeFeatures: Set<Feature> =", "static let freeFeatures: [Feature] =")
        with self.assertRaises(ValueError):
            mod.transform(changed)

if __name__=="__main__":
    unittest.main()
