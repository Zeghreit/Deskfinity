import json, os, time, unittest
from harness import df, Base, APP, load_json


class Rules(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(df.parse_rules("*.pdf; *.PDF, Скриншот*\n*/ ;;"),
                         ["*.pdf", "Скриншот*", "*/"])
        self.assertEqual(df.parse_rules("  "), [])

    def test_match(self):
        r = ["*.pdf", "скриншот*", "фото*/"]
        self.assertTrue(df.rules_match(r, "Report.PDF", False))
        self.assertTrue(df.rules_match(r, "Скриншот 2024.png", False))
        self.assertTrue(df.rules_match(r, "Фото отпуск", True))
        self.assertFalse(df.rules_match(r, "Фото отпуск", False))   # folder-only
        self.assertFalse(df.rules_match(r, "x.pdf", True))          # files-only
        self.assertFalse(df.rules_match(r, "notes.txt", False))
        self.assertTrue(df.rules_match(["*/"], "Anything", True))

    def test_skip(self):
        for name in ("~$doc.docx", "a.crdownload", "b.part", "c.TMP", "desktop.ini", ".hidden"):
            self.assertTrue(df.skip_for_sorting("/x/" + name), name)
        self.assertFalse(df.skip_for_sorting("/x/report.pdf"))


class AutoSort(Base):
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
        m.sorter._timer.setInterval(50)
        def cleanup():
            m._status_timer.stop(); m.sorter._timer.stop()
            [b.close() for b in m.boxes]; m._ipc.close(); m.tray.hide()
        self.addCleanup(cleanup)
        return m

    def standard(self):
        return self.manager([
            {"uid": "docs", "rules": ["*.pdf"]},
            {"uid": "pics", "rules": ["*.png", "Фото*/"]},
            {"uid": "plain"},
        ])

    def wait_for(self, cond, timeout=8):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            self.spin(30)
        return cond()

    def test_new_items_are_sorted_by_the_watcher(self):
        old = self.touch("Desktop", "old.pdf")
        m = self.standard()
        docs, pics = m.boxes[0], m.boxes[1]
        new_pdf = self.touch("Desktop", "new.pdf")
        png = self.touch("Desktop", "pic.png")
        txt = self.touch("Desktop", "note.txt")
        lock = self.touch("Desktop", "~$draft.pdf")
        folder = os.path.dirname(self.touch("Desktop", "Фото 2024", "x.jpg"))
        self.assertTrue(self.wait_for(lambda: not os.path.exists(new_pdf)
                                      and not os.path.exists(png)
                                      and not os.path.exists(folder)))
        self.assertEqual([os.path.basename(p) for p in docs.items], ["new.pdf"])
        self.assertEqual(sorted(os.path.basename(p) for p in pics.items), ["pic.png", "Фото 2024"])
        self.assertTrue(all(docs._in_store(p) for p in docs.items))
        for left in (old, txt, lock):       # existing, unmatched, temporary
            self.assertTrue(os.path.exists(left), left)

    def test_waits_until_item_settles(self):
        m = self.standard()
        df.DesktopSorter.SETTLE_S = 3600
        f = self.touch("Desktop", "fresh.pdf")
        m.sorter.scan()
        self.assertTrue(os.path.exists(f))
        self.assertTrue(m.sorter._timer.isActive())   # will look again
        df.DesktopSorter.SETTLE_S = 0
        self.assertTrue(self.wait_for(lambda: not os.path.exists(f)))

    def test_sent_back_to_desktop_is_not_resorted(self):
        m = self.standard()
        f = self.touch("Desktop", "keep.pdf")
        self.assertTrue(self.wait_for(lambda: not os.path.exists(f)))
        m.boxes[0]._remove(0)
        self.assertTrue(os.path.exists(f))
        self.spin(300)
        m.sorter.scan()
        self.assertTrue(os.path.exists(f))
        self.assertEqual(m.boxes[0].items, [])

    def test_file_in_use_is_retried_then_given_up(self):
        m = self.standard()
        real_move, calls = df.shutil.move, []
        def busy(src, dst):
            calls.append(src)
            if len(calls) < 3:
                raise PermissionError("in use")
            return real_move(src, dst)
        df.shutil.move = busy
        try:
            f = self.touch("Desktop", "busy.pdf")
            self.assertTrue(self.wait_for(lambda: not os.path.exists(f)))
        finally:
            df.shutil.move = real_move
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(m.boxes[0].items), 1)

        def never(src, dst):
            calls.append(src)
            raise PermissionError("in use")
        calls.clear()
        df.shutil.move = never
        try:
            g = self.touch("Desktop", "stuck.pdf")
            self.assertTrue(self.wait_for(lambda: "stuck.pdf" in m.sorter._seen))
            self.spin(300)
        finally:
            df.shutil.move = real_move
        self.assertEqual(len(calls), df.DesktopSorter.MAX_TRIES)
        self.assertTrue(os.path.exists(g))
        self.assertEqual(len(m.boxes[0].items), 1)

    def test_item_already_linked_by_a_box_is_left(self):
        f = self.touch("Desktop", "linked.pdf")
        m = self.manager([
            {"uid": "ref", "move_files": False, "items": [f]},
            {"uid": "docs", "rules": ["*.pdf"]},
        ])
        self.assertTrue(m.sort_item(f))
        self.assertTrue(os.path.exists(f))
        self.assertEqual(m.boxes[1].items, [])

    def test_first_matching_box_wins(self):
        m = self.manager([{"uid": "a", "rules": ["*.pdf"]}, {"uid": "b", "rules": ["*"]}])
        f = self.touch("Desktop", "x.pdf")
        g = self.touch("Desktop", "y.txt")
        m.sort_item(f); m.sort_item(g)
        self.assertEqual(len(m.boxes[0].items), 1)
        self.assertEqual(len(m.boxes[1].items), 1)

    def test_sort_desktop_now(self):
        a = self.touch("Desktop", "a.pdf")
        b = self.touch("Desktop", "b.png")
        c = self.touch("Desktop", "c.txt")
        m = self.standard()
        self.assertEqual(m.sort_desktop(only=m.boxes[1]), 1)
        self.assertTrue(os.path.exists(a) and not os.path.exists(b))
        self.assertEqual(m.sort_desktop(), 1)
        self.assertFalse(os.path.exists(a))
        self.assertTrue(os.path.exists(c))

    def test_rules_persist(self):
        m = self.standard()
        m._write()
        saved = load_json(df.CONFIG_PATH)["boxes"]
        self.assertEqual(saved[1]["rules"], ["*.png", "Фото*/"])
        self.assertEqual(saved[2]["rules"], [])

    def test_dialog_presets(self):
        dlg = df.RulesDialog("Docs", ["*.pdf"])
        self.addCleanup(dlg.close)
        dlg.add(dict(df.RULE_PRESETS)["Документы"])
        pats = dlg.patterns()
        self.assertEqual(pats[0], "*.pdf")
        self.assertEqual(pats.count("*.pdf"), 1)
        self.assertIn("*.docx", pats)


if __name__ == "__main__":
    unittest.main()
