"""Landscape fullscreen guest video must not restore stale portrait frame."""
from pathlib import Path
import importlib.util
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v139_video',ROOT/'scripts/patch_v139_landscape_video_viewport.py')
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class LandscapeVideoViewport(unittest.TestCase):
    def test_orientation_frame_ownership(self):
        source=(ROOT/'scripts/patch_v139_landscape_video_viewport.py').read_text()
        self.assertIn('if (!self.isMaximized)',source)
        self.assertIn('nrgV139RequestGuestVideoOrientation:baseSettings.interfaceOrientation',source)
        self.assertIn('requestGeometryUpdateWithPreferences:preferences',source)
        self.assertIn('UIDeviceOrientationIsLandscape(device)',source)
        self.assertIn('SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY',source)
        self.assertIn('self.view.window.windowScene',source)
        self.assertNotIn('application.keyWindow',source)

    def test_unsupported_source_rejected(self):
        with self.assertRaises(ValueError):p.decorated('unverified orientation source')

    def test_generated_source_if_available(self):
        path=os.environ.get('V139_PATCHED_LIVECONTAINER')
        if not path:return
        source=(Path(path)/p.SOURCE).read_text()
        self.assertEqual(p.decorated(source),source)
        self.assertEqual(source.count('SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY'),1)
        self.assertIn('orientation=request_rejected',source)
        self.assertIn('if (!self.isMaximized)',source)

if __name__=='__main__':unittest.main()
