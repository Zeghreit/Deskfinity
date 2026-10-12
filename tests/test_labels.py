import os, unittest
from harness import df, Base, FakeManager


class Labels(Base):
    def labels(self, items, status):
        df.STATUS.clear()
        df.STATUS.update(status)
        b = df.Box(FakeManager(), {"items": items, "geometry": [0, 0, 600, 300]})
        self.addCleanup(b.close)
        seen = []
        b._draw_wrapped = lambda p, rect, text, fm: seen.append(text)
        b.show()
        self.spin(30)
        seen.clear()
        b.repaint()
        return seen[1::2]  # each label is drawn twice (shadow + text)

    def test_folder_with_dot_keeps_full_name(self):
        d = os.path.join(self.root, "Project.v2")
        f = os.path.join(self.root, "report.pdf")
        r = os.path.join(self.root, "Тест.lnk")
        st = {d: (True, True), f: (True, False), r: (True, False)}
        self.assertEqual(self.labels([d, f, r], st), ["Project.v2", "report", "Тест"])

    def test_drive_root_falls_back_to_path(self):
        self.assertEqual(self.labels(["/"], {"/": (True, True)}), ["/"])


if __name__ == "__main__":
    unittest.main()
