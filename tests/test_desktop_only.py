import os
from harness import df, Base, FakeManager
import unittest


class DesktopOnlyMove(Base):
    def test_desktop_file_is_moved(self):
        src = self.touch("Desktop", "a.txt")
        box = df.Box(FakeManager(), {"move_files": True})
        self.assertEqual(box.add_paths([src]), 1)
        self.assertFalse(os.path.exists(src))
        self.assertTrue(box._in_store(box.items[0]))
        self.assertTrue(os.path.exists(box.items[0]))

    def test_other_folder_file_is_referenced(self):
        src = self.touch("Projects", "big", "main.py")
        folder = os.path.dirname(src)
        box = df.Box(FakeManager(), {"move_files": True})
        box.add_paths([folder, src])
        self.assertTrue(os.path.exists(folder) and os.path.exists(src))
        self.assertEqual(box.items, [os.path.normpath(folder), os.path.normpath(src)])

    def test_desktop_subfolder_item_is_referenced(self):
        src = self.touch("Desktop", "sub", "b.txt")
        box = df.Box(FakeManager(), {"move_files": True})
        box.add_paths([src])
        self.assertTrue(os.path.exists(src))

    def test_desktop_folder_is_moved(self):
        src = self.touch("Desktop", "Folder.v2", "c.txt")
        folder = os.path.dirname(src)
        box = df.Box(FakeManager(), {"move_files": True})
        box.add_paths([folder])
        self.assertFalse(os.path.exists(folder))
        self.assertTrue(os.path.isdir(box.items[0]))

    def test_move_off_keeps_desktop_file(self):
        src = self.touch("Desktop", "d.txt")
        box = df.Box(FakeManager(), {"move_files": False})
        box.add_paths([src])
        self.assertTrue(os.path.exists(src))

    def test_migrate_only_moves_desktop_items(self):
        a = self.touch("Desktop", "e.txt")
        b = self.touch("Elsewhere", "f.txt")
        box = df.Box(FakeManager(), {"move_files": True, "items": [a, b]})
        box.migrate_originals()
        self.assertFalse(os.path.exists(a))
        self.assertTrue(os.path.exists(b))
        self.assertEqual(box.items[1], b)

    def test_eject_roundtrip(self):
        src = self.touch("Desktop", "g.txt")
        box = df.Box(FakeManager(), {"move_files": True})
        box.add_paths([src])
        box._remove(0)
        self.assertTrue(os.path.exists(src))
        self.assertEqual(box.items, [])


if __name__ == "__main__":
    unittest.main()
