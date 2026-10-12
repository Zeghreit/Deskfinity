import os, threading, time, unittest
from harness import df, Base, APP


class Status(Base):
    def manager(self, items):
        df.STATUS.clear()
        m = df.Manager(APP)
        b = df.Box(m, {"uid": "s", "items": items, "geometry": [0, 0, 400, 300]})
        m.boxes.append(b)
        b.show()
        def cleanup():
            m._status_timer.stop()
            b.close()
            m._ipc.close()
            m.tray.hide()
        self.addCleanup(cleanup)
        return m, b

    def wait_for(self, cond, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            self.spin(20)
        return False

    def test_status_is_collected_off_thread(self):
        f = self.touch("Elsewhere", "a.txt")
        d = os.path.dirname(f)
        gone = os.path.join(self.root, "missing.txt")
        m, b = self.manager([f, d, gone])
        m.request_status()
        self.assertTrue(self.wait_for(lambda: gone in df.STATUS and d in df.STATUS and not m._status_busy))
        self.assertEqual(df.STATUS[f], (True, False))
        self.assertEqual(df.STATUS[d], (True, True))
        self.assertEqual(df.STATUS[gone], (False, False))
        os.remove(f)
        m.request_status()
        self.assertTrue(self.wait_for(lambda: df.STATUS[f] == (False, False)))

    def test_paint_never_touches_the_disk(self):
        items = [self.touch("Elsewhere", f"{i}.txt") for i in range(6)]
        m, b = self.manager(items)
        self.assertTrue(self.wait_for(lambda: all(p in df.STATUS for p in items) and not m._status_busy))
        main = threading.get_ident()
        calls = []
        real_exists = os.path.exists

        def slow_exists(p):
            if threading.get_ident() == main:
                calls.append(p)
            time.sleep(0.3)
            return real_exists(p)
        os.path.exists = slow_exists
        try:
            t = time.perf_counter()
            for _ in range(5):
                b.repaint()
            elapsed = time.perf_counter() - t
        finally:
            os.path.exists = real_exists
        self.assertEqual(calls, [])
        self.assertLess(elapsed, 0.5)

    def test_unknown_item_triggers_a_check(self):
        m, b = self.manager([])
        self.wait_for(lambda: not m._status_busy)
        f = self.touch("Elsewhere", "new.txt")
        b.items.append(f)
        b.repaint()
        self.assertTrue(self.wait_for(lambda: f in df.STATUS))

    def test_requests_coalesce_while_busy(self):
        m, b = self.manager([self.touch("Elsewhere", "x.txt")])
        self.wait_for(lambda: not m._status_busy)
        runs = []
        real_check = m._check_status

        def counting(paths):           # this manager's checks only
            runs.append(1)
            real_check(paths)
        m._check_status = counting
        for _ in range(10):
            m.request_status()
        self.wait_for(lambda: not m._status_busy and not m._status_again)
        self.spin(100)
        self.assertEqual(len(runs), 2)  # the first, plus one follow-up


if __name__ == "__main__":
    unittest.main()
