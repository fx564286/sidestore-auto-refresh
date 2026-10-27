import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class RotationGeometryRegression(unittest.TestCase):
    def test_safe_area_is_not_treated_as_stale_guest(self):
        src = (ROOT / "scripts/patch_v55_rotation_geometry.py").read_text()
        self.assertIn("CGSize viewportSize = self.view.bounds.size;", src)
        self.assertIn("fabs(guestSize.width - viewportSize.width)", src)
        self.assertIn("fabs(guestSize.height - viewportSize.height)", src)
        self.assertNotIn("fabs(guestSize.width - size.width)", src)

if __name__ == "__main__":
    unittest.main()
