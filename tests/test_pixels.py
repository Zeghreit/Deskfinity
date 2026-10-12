import random, unittest
from PyQt6 import QtGui
from PyQt6.QtCore import QRect
from harness import df, Base


def old_content_rect(img):
    """Verbatim copy of the original implementation."""
    w, h = img.width(), img.height()
    ptr = img.constBits(); ptr.setsize(img.sizeInBytes())
    data = bytes(ptr); bpl = img.bytesPerLine()
    left, top, right, bottom = w, h, -1, -1
    step = 1 if w <= 64 else 2
    for y in range(0, h, step):
        base = y * bpl
        row = data[base:base + w * 4]
        alphas = row[3::4]
        if not any(a > 8 for a in alphas):
            continue
        if y < top: top = y
        bottom = y
        for x in range(0, w, step):
            if alphas[x] > 8:
                if x < left: left = x
                if x > right: right = x
    if right < 0:
        return QRect(0, 0, w, h)
    pad = step
    left = max(0, left - pad); top = max(0, top - pad)
    right = min(w - 1, right + pad); bottom = min(h - 1, bottom + pad)
    return QRect(left, top, right - left + 1, bottom - top + 1)


def exact_rect(img, pad=1):
    w, h = img.width(), img.height()
    pts = [(x, y) for y in range(h) for x in range(w) if img.pixelColor(x, y).alpha() > 8]
    if not pts:
        return QRect(0, 0, w, h)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    l, t = max(0, min(xs) - pad), max(0, min(ys) - pad)
    r, b = min(w - 1, max(xs) + pad), min(h - 1, max(ys) + pad)
    return QRect(l, t, r - l + 1, b - t + 1)


def icon_like(w, h, box, alpha_lo=0):
    img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtGui.QColor(0, 0, 0, 0))
    x0, y0, x1, y1 = box
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            img.setPixelColor(x, y, QtGui.QColor(200, 100, 50, random.randint(max(9, alpha_lo), 255)))
    # faint noise that must be ignored (alpha <= 8)
    for _ in range(30):
        img.setPixelColor(random.randrange(w), random.randrange(h), QtGui.QColor(0, 0, 0, random.randint(1, 8)))
    return img


class Pixels(Base):
    def test_content_rect_exact(self):
        random.seed(1)
        for w in (16, 32, 48, 63, 64, 65, 100):
            for _ in range(4):
                x0, y0 = random.randrange(w), random.randrange(w)
                x1, y1 = random.randrange(x0, w), random.randrange(y0, w)
                img = icon_like(w, w, (x0, y0, x1, y1))
                self.assertEqual(df._content_rect(img), exact_rect(img), (w, x0, y0, x1, y1))

    def test_matches_old_within_its_sampling_error(self):
        random.seed(2)
        for w in (32, 48, 256):
            img = icon_like(w, w, (w // 4, w // 5, w - w // 3, w - w // 6))
            new, old = df._content_rect(img), old_content_rect(img)
            for a, b in ((new.left(), old.left()), (new.top(), old.top()),
                         (new.right(), old.right()), (new.bottom(), old.bottom())):
                self.assertLessEqual(abs(a - b), 2, (w, new, old))

    def test_empty_and_full(self):
        img = QtGui.QImage(256, 256, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(0, 0, 0, 0))
        self.assertEqual(df._content_rect(img), QRect(0, 0, 256, 256))
        img.fill(QtGui.QColor(1, 2, 3, 255))
        self.assertEqual(df._content_rect(img), QRect(0, 0, 256, 256))

    def test_alpha_from_mask_matches_old_loop(self):
        random.seed(3)
        w = h = 64
        mraw = bytes(random.choice((0, 255)) if i % 4 == 0 else random.randrange(256)
                     for i in range(w * h * 4))
        old = bytearray(w * h * 4)
        for i in range(w * h):
            old[i * 4 + 3] = 0 if mraw[i * 4] else 255
        new = bytearray(w * h * 4)
        new[3::4] = df._alpha_from_mask(mraw)
        self.assertEqual(new, old)


if __name__ == "__main__":
    unittest.main()
