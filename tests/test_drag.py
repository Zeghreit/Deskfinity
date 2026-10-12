import json, os, shutil, unittest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, QPointF
from harness import df, Base, APP, load_json

NONE = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier


def mouse(box, kind, idx, mods=NONE):
    box._relayout()
    pt = QPointF(box._rects[idx].center()) if idx >= 0 else QPointF(box.width() / 2, box.height() - 20)
    ev = QtGui.QMouseEvent(kind, pt, QPointF(box.mapToGlobal(pt.toPoint())),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, mods)
    if kind == QtCore.QEvent.Type.MouseButtonPress:
        box.mousePressEvent(ev)
    else:
        box.mouseReleaseEvent(ev)


def click(box, idx, mods=NONE):
    mouse(box, QtCore.QEvent.Type.MouseButtonPress, idx, mods)
    mouse(box, QtCore.QEvent.Type.MouseButtonRelease, idx, mods)


def drop(target, mime, idx=None):
    target._relayout()
    if idx is not None:   # left part of an icon = insert before it
        r = target._rects[idx]
        pt = QPointF(r.left() + 5, r.center().y())
    else:
        pt = QPointF(20, target.height() - 10)
    ev = QtGui.QDropEvent(pt, Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, NONE)
    target.dropEvent(ev)
    return ev


class Drag(Base):
    def setUp(self):
        super().setUp()
        self._settle = df.DesktopSorter.SETTLE_S
        df.DesktopSorter.SETTLE_S = 0

    def tearDown(self):
        df.DesktopSorter.SETTLE_S = self._settle
        super().tearDown()

    def manager(self, boxes):
        os.makedirs(df.CONFIG_DIR, exist_ok=True)
        with open(df.CONFIG_PATH, "w") as fh:
            json.dump({"boxes": boxes}, fh)
        m = df.Manager(APP)
        def cleanup():
            m._status_timer.stop(); m.sorter._timer.stop()
            [b.close() for b in m.boxes]; m._ipc.close(); m.tray.hide()
        self.addCleanup(cleanup)
        return m

    def two(self, n=5, rules=None):
        files = [self.touch("Elsewhere", f"{c}.txt") for c in "abcdefgh"[:n]]
        m = self.manager([
            {"uid": "A", "items": files, "geometry": [0, 0, 700, 400]},
            {"uid": "B", "items": [], "geometry": [0, 400, 700, 300], "rules": rules or []},
        ])
        return m, m.boxes[0], m.boxes[1], files

    def stored(self, box, name):
        src = self.touch("Desktop", name)
        box.add_paths([src])
        return box.items[-1]

    # ---- selection ----
    def test_click_ctrl_shift_selection(self):
        m, a, b, f = self.two()
        click(a, 1)
        self.assertEqual(a.selection(), [f[1]])
        click(a, 3, CTRL)
        self.assertEqual(a.selection(), [f[1], f[3]])
        click(a, 1, CTRL)
        self.assertEqual(a.selection(), [f[3]])
        click(a, 0, SHIFT)              # anchor = last Ctrl+click (1), like Explorer
        self.assertEqual(a.selection(), f[0:2])
        click(a, 3, SHIFT)
        self.assertEqual(a.selection(), f[1:4])
        click(a, 2)                     # plain click inside: collapses on release
        self.assertEqual(a.selection(), [f[2]])
        click(a, -1)                    # empty area
        self.assertEqual(a.selection(), [])

    def test_press_on_selected_keeps_group_for_drag(self):
        m, a, b, f = self.two()
        click(a, 0); click(a, 2, CTRL)
        mouse(a, QtCore.QEvent.Type.MouseButtonPress, 2)
        self.assertEqual(a.selection(), [f[0], f[2]])

    def test_one_selection_across_boxes(self):
        m, a, b, f = self.two()
        b.add_paths([self.touch("Elsewhere", "z.txt")])
        click(a, 0)
        click(b, 0)
        self.assertEqual(a.selection(), [])
        self.assertEqual(len(b.selection()), 1)

    def test_locked_box_selects_but_does_not_drag(self):
        m, a, b, f = self.two()
        a.locked = True
        mouse(a, QtCore.QEvent.Type.MouseButtonPress, 1)
        self.assertEqual(a._drag_index, -1)
        self.assertEqual(a.selection(), [f[1]])

    # ---- reorder ----
    def test_reorder(self):
        m, a, b, f = self.two()
        A, B, C, D, E = f
        a.reorder([B, D], 5)
        self.assertEqual(a.items, [A, C, E, B, D])
        a.items = list(f)
        a.reorder([A, B], 3)
        self.assertEqual(a.items, [C, A, B, D, E])
        a.items = list(f)
        a.reorder([E], 0)
        self.assertEqual(a.items, [E, A, B, C, D])

    def test_drop_on_same_box_reorders(self):
        m, a, b, f = self.two()
        drop(a, a._make_mime([f[0]]), idx=3)
        self.assertEqual(a.items, [f[1], f[2], f[0], f[3], f[4]])

    # ---- between boxes ----
    def test_drop_on_other_box_moves_links_and_files(self):
        m, a, b, f = self.two(n=2)
        s = self.stored(a, "doc.pdf")
        self.assertTrue(a._in_store(s))
        drop(b, a._make_mime([f[0], s]))
        self.assertEqual(a.items, [f[1]])
        self.assertEqual(len(b.items), 2)
        self.assertEqual(b.items[0], f[0])           # a link stays a link
        self.assertTrue(b._in_store(b.items[1]))     # a stored file follows
        self.assertTrue(os.path.exists(b.items[1]))
        self.assertFalse(os.path.exists(s))
        self.assertEqual(b.selection(), b.items)
        m._write()
        saved = load_json(df.CONFIG_PATH)["boxes"]
        self.assertEqual(len(saved[0]["items"]) + len(saved[1]["items"]), 3)

    def test_drop_at_position(self):
        m, a, b, f = self.two(n=4)
        b.add_paths([self.touch("Elsewhere", "x.txt"), self.touch("Elsewhere", "y.txt")])
        drop(b, a._make_mime([f[2]]), idx=1)
        self.assertEqual(os.path.basename(b.items[1]), "c.txt")

    def test_desktop_link_is_moved_in_when_target_moves_files(self):
        d = self.touch("Desktop", "on-desk.txt")
        m = self.manager([
            {"uid": "A", "move_files": False, "items": [d]},
            {"uid": "B"},
        ])
        a, b = m.boxes
        b.take_from(a, [d])
        self.assertFalse(os.path.exists(d))
        self.assertTrue(b._in_store(b.items[0]))

    def test_file_in_use_stays_in_source(self):
        m, a, b, f = self.two(n=0)
        s = self.stored(a, "locked.pdf")
        real = df.shutil.move
        df.shutil.move = lambda *x: (_ for _ in ()).throw(PermissionError("in use"))
        try:
            self.assertEqual(b.take_from(a, [s]), 0)
        finally:
            df.shutil.move = real
        self.assertEqual(a.items, [s])
        self.assertEqual(b.items, [])

    def test_stale_or_foreign_mime_is_ignored(self):
        m, a, b, f = self.two(n=1)
        mime = QtCore.QMimeData()
        mime.setData(df.ITEMS_MIME, b'{"box": "nope", "paths": ["x"]}')
        drop(b, mime)
        mime.setData(df.ITEMS_MIME, b"garbage")
        drop(b, mime)
        self.assertEqual((a.items, b.items), (f, []))

    def test_external_file_drop_still_adds(self):
        m, a, b, f = self.two(n=0)
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(self.touch("Desktop", "new.txt"))])
        drop(b, mime)
        self.assertEqual(len(b.items), 1)

    # ---- full drag with a simulated drop target ----
    def start_drag(self, box, idx, on_drop):
        box._drag_index = idx
        box._exec_drag = on_drop
        box._start_drag()

    def test_drag_selection_to_other_box(self):
        m, a, b, f = self.two()
        click(a, 0); click(a, 3, CTRL)
        def to_b(drag):
            self.assertEqual(len(drag.mimeData().urls()), 2)
            drop(b, drag.mimeData())
            return Qt.DropAction.MoveAction
        self.start_drag(a, 3, to_b)
        self.assertEqual(b.items, [f[0], f[3]])
        self.assertEqual(a.items, [f[1], f[2], f[4]])

    def test_drag_to_desktop_explorer_moves_it(self):
        m, a, b, f = self.two(n=0, rules=["*.pdf"])
        self.stored(a, "back.pdf")
        target = os.path.join(self.desktop, "back.pdf")
        def explorer_move(drag):
            shutil.move(drag.mimeData().urls()[0].toLocalFile(), target)
            return Qt.DropAction.IgnoreAction    # optimized move reports nothing
        self.start_drag(a, 0, explorer_move)
        self.assertEqual(a.items, [])
        m.sorter.scan()                           # B's rule matches *.pdf
        self.assertTrue(os.path.exists(target))
        self.assertEqual(b.items, [])

    def test_late_explorer_move_is_noticed(self):
        m, a, b, f = self.two(n=0, rules=["*.pdf"])
        s = self.stored(a, "slow.pdf")
        target = os.path.join(self.desktop, "slow.pdf")
        self.start_drag(a, 0, lambda drag: Qt.DropAction.MoveAction)
        self.assertEqual(a.items, [s])            # nothing moved yet
        m.sorter.scan()                           # a scan before the file lands
        shutil.move(s, target)                    # Explorer finishes later
        self.spin(1700)
        self.assertEqual(a.items, [])
        m.sorter.scan()
        self.assertTrue(os.path.exists(target))
        self.assertEqual(b.items, [])

    def test_copy_out_keeps_item(self):
        m, a, b, f = self.two(n=0)
        s = self.stored(a, "copy.pdf")
        def explorer_copy(drag):
            shutil.copy(s, os.path.join(self.root, "copy.pdf"))
            return Qt.DropAction.CopyAction
        self.start_drag(a, 0, explorer_copy)
        self.assertEqual(a.items, [s])

    def test_drag_badge_pixmap(self):
        m, a, b, f = self.two()
        pm = a._drag_pixmap(f[:3])
        self.assertFalse(pm.isNull())

    # ---- menu actions ----
    def test_send_selection_to_desktop(self):
        m, a, b, f = self.two(n=0)
        s1, s2 = self.stored(a, "one.pdf"), self.stored(a, "two.pdf")
        a._remove_paths([s1, s2])
        self.assertEqual(a.items, [])
        self.assertTrue(os.path.exists(os.path.join(self.desktop, "one.pdf")))
        self.assertTrue(os.path.exists(os.path.join(self.desktop, "two.pdf")))


if __name__ == "__main__":
    unittest.main()
