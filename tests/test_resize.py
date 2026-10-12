import unittest
from PyQt6.QtCore import QPoint
from harness import df, Base, FakeManager


class Resize(Base):
    def make(self, collapsed=False):
        b = df.Box(FakeManager(), {"geometry": [100, 100, 300, 250], "collapsed": collapsed})
        self.addCleanup(b.close)
        return b

    def drag(self, b, direction, dx, dy):
        b._press_geo = b.geometry()
        b._press_pos = QPoint(0, 0)
        b._resize_dir = direction
        b._do_resize(QPoint(dx, dy))

    def test_collapsed_header_has_no_vertical_edges(self):
        b = self.make(collapsed=True)
        self.assertEqual(b.height(), df.HEADER_H)
        self.assertEqual(b._edge_at(QPoint(150, 2)), "")
        self.assertEqual(b._edge_at(QPoint(150, df.HEADER_H - 2)), "")
        self.assertEqual(b._edge_at(QPoint(2, 2)), "l")
        self.assertEqual(b._edge_at(QPoint(298, 20)), "r")

    def test_collapsed_width_resize_keeps_it_collapsed(self):
        b = self.make(collapsed=True)
        self.drag(b, "r", 80, 300)
        self.assertEqual(b.height(), df.HEADER_H)
        self.assertEqual(b.width(), 380)
        self.assertEqual(b.to_dict()["geometry"][3], 250)  # expanded height kept
        b.toggle_collapse()
        self.assertEqual(b.height(), 250)

    def test_expanded_corner_resize(self):
        b = self.make()
        self.drag(b, "br", 40, 30)
        self.assertEqual((b.width(), b.height()), (340, 280))
        self.assertEqual(b._expanded_h, 280)

    def test_left_edge_stops_at_min_width(self):
        b = self.make()
        right = b.geometry().right()
        self.drag(b, "l", 1000, 0)
        self.assertEqual(b.width(), df.MIN_W)
        self.assertEqual(b.geometry().right(), right)

    def test_top_edge_stops_at_min_height(self):
        b = self.make()
        bottom = b.geometry().bottom()
        self.drag(b, "t", 0, 1000)
        self.assertEqual(b.height(), df.MIN_H)
        self.assertEqual(b.geometry().bottom(), bottom)

    def test_right_edge_min_width(self):
        b = self.make()
        left = b.x()
        self.drag(b, "r", -1000, 0)
        self.assertEqual((b.x(), b.width()), (left, df.MIN_W))


if __name__ == "__main__":
    unittest.main()
