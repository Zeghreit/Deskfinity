import ast, re, unittest
from harness import df, Base, APP

CYR = re.compile(r"[А-Яа-яЁё]")
# shown as-is in both languages
ALLOWED = {"Русский", "Язык / Language"}


class Translations(unittest.TestCase):
    def test_every_russian_string_has_an_english_twin(self):
        with open(df.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node

        def inside_tr_first_arg(node):
            while node in parent:
                up = parent[node]
                if isinstance(up, ast.Call) and getattr(up.func, "id", "") == "tr":
                    return up.args and (node is up.args[0])
                node = up
            return False

        def in_presets(node):
            while node in parent:
                node = parent[node]
                if isinstance(node, ast.Assign) and any(
                        getattr(t, "id", "") == "RULE_PRESETS" for t in node.targets):
                    return True
            return False

        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and CYR.search(node.value) and node.value not in ALLOWED:
                if not (inside_tr_first_arg(node) or in_presets(node)):
                    bad.append((node.lineno, node.value[:40]))
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "tr":
                self.assertEqual(len(node.args), 2, node.lineno)
                for sub in ast.walk(node.args[1]):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        self.assertIsNone(CYR.search(sub.value), (node.lineno, sub.value))
        self.assertEqual(bad, [])

    def test_nothing_shadows_tr(self):
        with open(df.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        clashes = [n.lineno for n in ast.walk(tree)
                   if (isinstance(n, ast.Name) and n.id == "tr"
                       and isinstance(n.ctx, ast.Store))
                   or (isinstance(n, ast.arg) and n.arg == "tr")]
        self.assertEqual(clashes, [])

    def test_tr_switches(self):
        try:
            df.set_language("en")
            self.assertEqual(df.tr("Да", "Yes"), "Yes")
            df.set_language("ru")
            self.assertEqual(df.tr("Да", "Yes"), "Да")
            df.set_language("auto")
            self.assertIn(df.LANG, ("ru", "en"))
        finally:
            df.set_language("ru")


class Switch(Base):
    def manager(self):
        m = df.Manager(APP)
        def cleanup():
            m._status_timer.stop(); m.sorter._timer.stop()
            [b.close() for b in m.boxes]; m._ipc.close(); m.tray.hide()
            df.set_language("ru")
        self.addCleanup(cleanup)
        return m

    def texts(self, m):
        return [a.text() for a in m._tray_menu.actions() if a.text()]

    def test_switch_rebuilds_menu_and_persists(self):
        m = self.manager()
        m.set_ui_language("en")
        self.assertIn("Quit", self.texts(m))
        self.assertIn("New group", self.texts(m))
        m.set_ui_language("ru")
        self.assertIn("Выход", self.texts(m))
        m.set_ui_language("en")
        m._write()
        m2 = self.manager()
        self.assertEqual(df.LANG, "en")
        self.assertIn("Show all", self.texts(m2))

    def test_new_box_title_follows_language(self):
        m = self.manager()
        m.set_ui_language("en")
        self.assertEqual(df.Box(m, {}).title, "New group")


if __name__ == "__main__":
    unittest.main()
