from pathlib import Path
import json,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
N=(ROOT/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
X=(ROOT/"HostApp/ScarletAuthXPCSupport.swift").read_text()
R=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
class NativeErrorEvidence(unittest.TestCase):
    def test_original_dispatch_error_survives(self):
        self.assertNotIn("try? AppManager.shared.backgroundRefresh(",N)
        self.assertIn("let operation = try AppManager.shared.backgroundRefresh(",N)
        self.assertIn("continuation.resume(throwing: error)",N)
        self.assertEqual(N.count("reply(false, failureReceipt(error, stage: stage))"),2)
        self.assertIn("depth < 4",N)
        self.assertIn("visited.insert(ObjectIdentifier(next)).inserted",N)
        helper=N.split("private static func failureReceipt(",1)[1].split("@objc static func perform",1)[0]
        for forbidden in ("localizedDescription","debugDescription","userInfo.description","password","token"):
            self.assertNotIn(forbidden,helper)
    def test_host_uses_only_closed_domain_and_kind_fields(self):
        self.assertIn("allowed.contains(candidateReason)",X)
        self.assertIn("CustomNSError",X)
        self.assertIn('code.userInfo["ScarletNativeRefreshEvidence"]',R)
        for key in ('native_error_stage', 'native_error_domain', 'native_error_code', 'native_error_kind', 'native_underlying_domain', 'native_underlying_code', 'native_underlying_kind', 'native_error_depth'):
            self.assertIn('"'+key+'"',X)
            self.assertIn('"'+key+'"',R)
    def test_actual_swift_decoder_refuses_bad_payloads(self):
        swift=shutil.which("swiftc")
        if not swift:self.skipTest("Swift compiler available in native Xcode CI")
        source=X.split("// R6P34_NATIVE_EVIDENCE_BEGIN",1)[1].split("// R6P34_NATIVE_EVIDENCE_END",1)[0]
        base=dict(v=1,reason="native_unknown_appmanager_stage",stage="refresh",domain="operation",
                  code=1,kind="unknown_result",underlyingDomain="url",underlyingCode=-1005,
                  underlyingKind="other",depth=1)
        cases=[("scarlet_native_failure:"+json.dumps(base),True)]
        for key,val in [("v",2),("domain","user@example.test"),("stage","secret"),
                        ("kind","arbitrary"),("code",2147483648),("underlyingCode",-2147483649),
                        ("depth",5),("underlyingDomain","secret"),("underlyingKind","secret")]:
            item=dict(base);item[key]=val
            cases.append(("scarlet_native_failure:"+json.dumps(item),False))
        cases.extend([("native_unknown_appmanager_stage",False),("scarlet_native_failure:{",False),
                      ("scarlet_native_failure:"+"x"*1025,False)])
        # Swift executes the production decoder, not a Python model of it.
        checks="\n".join("precondition((ScarletNativeRefreshEvidence.decode("+
               json.dumps(wire)+") != nil) == "+str(ok).lower()+")" for wire,ok in cases)
        code="import Foundation\n"+source+"\n"+checks+"\nprint(\"DECODER_PASS\")\n"
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/"main.swift";out=Path(folder)/"test";src.write_text(code)
            subprocess.run([swift,str(src),"-o",str(out)],check=True,capture_output=True,text=True)
            done=subprocess.run([str(out)],check=True,capture_output=True,text=True)
            self.assertIn("DECODER_PASS",done.stdout)
if __name__=="__main__":unittest.main()
