import unittest
from PyQt6.QtCore import QPoint, QRect
from harness import df, Base, FakeManager


class Snap(Base):
    def setUp(self):
        super().setUp()
        self._areas = df.screen_areas
        df.screen_areas = lambda: [QRect(0, 0, 1000, 800)]
        self.m = FakeManager()
        self.m.boxes = []

    def tearDown(self):
        df.screen_areas = self._areas
        super().tearDown()

    def box(self, x, y, w=200, h=150):
        b = df.Box(self.m, {"geometry": [x, y, w, h]})
        self.m.boxes.append(b)
        b.show()
        self.addCleanup(b.close)
        return b

    def test_sticks_to_screen_edges(self):
        b = self.box(300, 300)
        self.assertEqual(b._snapped(QPoint(7, 300)), QPoint(0, 300))
        self.assertEqual(b._snapped(QPoint(795, 645)), QPoint(800, 650))  # right/bottom
        self.assertEqual(b._snapped(QPoint(300, 300)), QPoint(300, 300))  # far: free

    def test_sits_next_to_a_box_with_a_gap(self):
        self.box(100, 100)                       # spans x 100..299
        b = self.box(600, 100)
        p = b._snapped(QPoint(300 + df.SNAP_GAP + 4, 104))
        self.assertEqual(p.x(), 300 + df.SNAP_GAP)   # beside it
        self.assertEqual(p.y(), 100)                  # tops aligned

    def test_far_boxes_do_not_pull(self):
        self.box(100, 100)
        b = self.box(600, 500)
        self.assertEqual(b._snapped(QPoint(500, 500)), QPoint(500, 500))

    def test_stack_below_with_aligned_left_edge(self):
        self.box(100, 100)                       # bottom edge at y 249
        b = self.box(600, 500)
        p = b._snapped(QPoint(103, 250 + df.SNAP_GAP + 4))
        self.assertEqual(p, QPoint(100, 250 + df.SNAP_GAP))


if __name__ == "__main__":
    unittest.main()
