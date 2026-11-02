import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v172media",ROOT/"scripts/patch_v172_media_evidence.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MediaEvidence(unittest.TestCase):
    def test_notification_scope(self):
        source="// SCARLET_V172_RESTORE_PORTRAIT\n// SCARLET_V171_LANDSCAPE_SCENE_FRAME\n"+m.OLD+"\n"+m.HOOK
        out=m.patch(source)
        self.assertEqual(out,m.patch(out))
        self.assertIn("AVPlayerItemFailedToPlayToEndTimeNotification",out)
        self.assertIn("AVPlayerItemPlaybackStalledNotification",out)
        self.assertIn("AVAudioSessionInterruptionNotification",out)
        self.assertIn("content=redacted",out)
        self.assertNotIn("absoluteString",out)
        self.assertNotIn("playerItem.asset",out)
        self.assertIn("removeObserver:self",out)
    def test_fails_closed(self):
        with self.assertRaises(ValueError):m.patch(m.OLD)
if __name__=="__main__":unittest.main()
