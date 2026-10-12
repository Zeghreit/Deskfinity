import unittest
from harness import df, Base


class HiDpiIcons(Base):
    def test_pixmap_has_physical_pixels_and_logical_size(self):
        f = self.touch("Desktop", "a.txt")
        for dpr, size, px in ((1.0, 48, 48), (1.25, 48, 60), (1.5, 48, 72), (2.0, 96, 192)):
            pm = df.ICONS.get(f, size, dpr)
            self.assertEqual(max(pm.width(), pm.height()), px, (dpr, size))
            self.assertAlmostEqual(pm.devicePixelRatio(), dpr)
            self.assertLessEqual(max(pm.width(), pm.height()) / pm.devicePixelRatio(), size + 0.01)

    def test_cache_separates_scales(self):
        f = self.touch("Desktop", "b.txt")
        a = df.ICONS.get(f, 48, 1.0)
        b = df.ICONS.get(f, 48, 2.0)
        self.assertNotEqual(a.width(), b.width())
        self.assertIs(df.ICONS.get(f, 48, 2.0), b)

    def test_paint_on_scaled_screens(self):
        import os, subprocess, sys
        probe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dpi_probe.py")
        for scale, px in (("2", 96), ("1.5", 72)):
            env = dict(os.environ, QT_SCALE_FACTOR=scale)
            out = subprocess.run([sys.executable, probe], env=env, capture_output=True,
                                 text=True, timeout=60).stdout
            self.assertIn(f"px [{px}]", out, out)


if __name__ == "__main__":
    unittest.main()
