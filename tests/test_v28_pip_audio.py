"""V28 regression: PiP-only host audio session and no eager playback activation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/patch_v28_pip_audio.py"
UPSTREAM=Path("/shared/nrg-v27-upstream-livecontainer/MultitaskSupport/PiPManager.m")

def patch_mod():
    spec=importlib.util.spec_from_file_location("v28_pip_audio",SCRIPT)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class PiPAudioTests(unittest.TestCase):
    def test_pinned_source_audio_lifetime(self):
        if not UPSTREAM.is_file():
            self.skipTest("Source integration verified by build patch")
        m=patch_mod()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/m.FILE
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(UPSTREAM.read_bytes())
            m.patch(Path(d))
            s=p.read_text()
            self.assertIn(m.MARKER,s)
            init=s.split("- (instancetype)init {",1)[1].split("- (void)startPiPWithVC:",1)[0]
            self.assertNotIn("AVAudioSession",init)
            self.assertIn("[audioSession setActive:YES error:&audioError]",s)
            self.assertIn("AVAudioSessionSetActiveOptionNotifyOthersOnDeactivation",s)
            self.assertIn("pictureInPictureController:(",s)
            self.assertIn("failedToStartPictureInPictureWithError",s)
            before=p.read_bytes()
            m.patch(Path(d))
            self.assertEqual(before,p.read_bytes())

    def test_unknown_pip_source_fails_closed(self):
        m=patch_mod()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/m.FILE
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("unrecognized PiP source")
            with self.assertRaises(SystemExit):
                m.patch(Path(d))
            self.assertEqual(p.read_text(),"unrecognized PiP source")
if __name__=="__main__":
    unittest.main()
