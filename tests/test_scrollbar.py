import unittest
from harness import df, Base, FakeManager


class Scrollbar(Base):
    def box(self, n, h=200):
        items = [self.touch("Elsewhere", f"{i}.txt") for i in range(n)]
        b = df.Box(FakeManager(), {"items": items, "geometry": [0, 0, 300, h]})
        self.addCleanup(b.close)
        b._relayout()
        return b

    def test_hidden_when_everything_fits(self):
        self.assertIsNone(self.box(2)._scrollbar_rect())

    def test_tracks_scroll_position(self):
        b = self.box(40)
        top = b._scrollbar_rect()
        self.assertIsNotNone(top)
        self.assertEqual(top.top(), df.HEADER_H + 4)
        b._scroll = b._content_h - b.height()   # scrolled to the end
        end = b._scrollbar_rect()
        self.assertEqual(end.bottom(), b.height() - 4 - 1)
        self.assertEqual(end.height(), top.height())
        self.assertLess(top.height(), b.height() - df.HEADER_H)

    def test_hidden_when_collapsed(self):
        b = self.box(40)
        b.toggle_collapse()
        self.assertIsNone(b._scrollbar_rect())


if __name__ == "__main__":
    unittest.main()
