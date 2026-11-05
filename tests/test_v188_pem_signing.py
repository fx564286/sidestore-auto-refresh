"""V188 regression: OpenSSL 3 PFX is not required by rcodesign, Apple PEM key/cert do match."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main, mock
import os
import subprocess

SRC=Path(__file__).resolve().parents[1]/"scripts/scarlet_v188_sign_local.py"
spec=importlib.util.spec_from_file_location("v188_sign",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class PemSigningTests(TestCase):
    def pair(self, folder, prefix):
        key=folder/(prefix+".pem")
        cert=folder/(prefix+".crt")
        subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes",
                        "-keyout",str(key),"-out",str(cert),"-days","2",
                        "-subj","/CN=V188 local certificate test"],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        der=subprocess.check_output(["openssl","x509","-in",str(cert),"-outform","DER"])
        return key,cert,m.digest(der)

    def test_valid_pem_key_and_cert_match_original_certificate(self):
        with TemporaryDirectory() as d:
            key,cert,sha=self.pair(Path(d),"same")
            with mock.patch.object(m,"KEY",key),mock.patch.object(m,"CERT",cert):
                m.pem_identity_ready(sha)

    def test_mismatched_key_and_certificate_fail_closed(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            k1,c1,sha1=self.pair(root,"first")
            k2,c2,sha2=self.pair(root,"second")
            with mock.patch.object(m,"KEY",k1),mock.patch.object(m,"CERT",c2):
                with self.assertRaisesRegex(m.Blocked,"PEM_CERT_DIFFERS"):
                    m.pem_identity_ready(sha1)
                with self.assertRaisesRegex(m.Blocked,"APPLE_CERT_PRIVATE_KEY_MISMATCH"):
                    m.pem_identity_ready(sha2)

    def test_sign_uses_pem_sources_not_p12_decryption(self):
        with TemporaryDirectory() as d:
            fake=Path(d)/"rcodesign"
            fake.write_text("#!/bin/sh\nexit 0\n")
            fake.chmod(0o700)
            path=Path(d)/"Host.app"
            path.mkdir()
            exts={}
            for n in ("LiveProcess","ShareExtension","LaunchAppExtension"):
                exts[n]=Path(d)/(n+".appex")
                exts[n].mkdir()
            requests=[]
            def command(args,input=None):
                requests.append([str(x) for x in args])
                if "--help" in args:
                    return b"--pem-file --entitlements-xml-file --shallow"
                return b""
            with mock.patch.object(m,"RC",fake),mock.patch.object(m,"command",side_effect=command):
                m.sign(path,exts,Path(d))
            commands=[x for x in requests if len(x)>1 and x[1]=="sign" and "--help" not in x]
            self.assertEqual(len(commands),5)
            for c in commands:
                self.assertIn("--pem-file",c)
                self.assertIn(str(m.KEY),c)
                self.assertIn(str(m.CERT),c)
                self.assertNotIn("--p12-file",c)
                self.assertNotIn("--p12-password-file",c)

    def test_no_cert_rotation_or_secret_upload(self):
        s=SRC.read_text()
        for disallowed in ("revokeDevelopmentCert","submitDevelopmentCSR","deleteAppId",
                           "requests.post", "urllib.request.Request("):
            self.assertNotIn(disallowed,s)

if __name__=="__main__":
    main()
