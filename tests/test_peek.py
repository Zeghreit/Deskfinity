import unittest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, QPoint, QPointF
from harness import df, Base, FakeManager


class Peek(Base):
    def box(self, collapsed=True):
        b = df.Box(FakeManager(), {"geometry": [50, 50, 300, 260], "collapsed": collapsed})
        b.show()
        self.addCleanup(b.close)
        return b

    def test_open_and_close(self):
        b = self.box()
        self.assertTrue(b.shut)
        b._open_peek()
        self.assertFalse(b.shut)
        self.assertEqual(b.height(), 260)
        d = b.to_dict()
        self.assertTrue(d["collapsed"])
        self.assertEqual(d["geometry"][3], 260)
        b.leaveEvent(QtCore.QEvent(QtCore.QEvent.Type.Leave))
        self.assertTrue(b.shut)
        self.assertEqual(b.height(), df.HEADER_H)

    def test_hover_starts_timer_only_when_collapsed(self):
        b = self.box()
        b.enterEvent(QtGui.QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(55, 55)))
        self.assertTrue(b._peek_timer.isActive())
        e = self.box(collapsed=False)
        e.enterEvent(QtGui.QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(55, 55)))
        self.assertFalse(e._peek_timer.isActive())

    def test_resize_while_open_keeps_new_height(self):
        b = self.box()
        b._open_peek()
        b._press_geo = b.geometry()
        b._press_pos = QPoint(0, 0)
        b._resize_dir = "b"
        b._do_resize(QPoint(0, 40))
        self.assertEqual(b.height(), 300)
        b._close_peek()
        self.assertEqual(b.height(), df.HEADER_H)
        self.assertEqual(b.to_dict()["geometry"][3], 300)

    def test_drag_over_opens_and_leaving_closes(self):
        b = self.box()
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(self.touch("Desktop", "x.txt"))])
        ev = QtGui.QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime,
                                   Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        b.dragEnterEvent(ev)
        self.assertFalse(b.shut)
        b.dragLeaveEvent(QtGui.QDragLeaveEvent())
        self.assertTrue(b.shut)

    def test_toggle_while_open_expands_for_good(self):
        b = self.box()
        b._open_peek()
        b.toggle_collapse()
        self.assertFalse(b.collapsed)
        b.leaveEvent(QtCore.QEvent(QtCore.QEvent.Type.Leave))
        self.assertEqual(b.height(), 260)

    def test_expanded_box_unaffected(self):
        b = self.box(collapsed=False)
        b._open_peek()
        b._close_peek()
        self.assertEqual(b.height(), 260)


if __name__ == "__main__":
    unittest.main()
