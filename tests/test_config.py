import glob, json, os, unittest
from harness import df, Base, APP, load_json


def box(uid, title="B", **kw):
    d = {"uid": uid, "title": title, "geometry": [10, 10, 300, 200]}
    d.update(kw)
    return d


class ConfigSafety(Base):
    def write_cfg(self, content, path=None):
        path = path or df.CONFIG_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content if isinstance(content, str) else json.dumps(content))

    def read_cfg(self):
        with open(df.CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)

    def manager(self):
        m = df.Manager(APP)
        self.addCleanup(lambda: [b.close() for b in m.boxes])
        self.addCleanup(m.tray.hide)
        return m

    def test_good_config_loads_and_is_backed_up(self):
        self.write_cfg({"version": 1, "boxes": [box("a"), box("b")]})
        m = self.manager()
        self.assertEqual([b.uid for b in m.boxes], ["a", "b"])
        self.assertTrue(os.path.exists(df.CONFIG_PATH + ".bak1"))
        self.assertIsNone(m.load_notice)

    def test_corrupt_config_is_quarantined_not_overwritten(self):
        self.write_cfg('{"version": 1, "boxes": [ {"uid": "a"')  # truncated
        m = self.manager()
        self.assertEqual(m.boxes, [])
        self.assertIsNotNone(m.load_notice)
        broken = glob.glob(df.CONFIG_PATH + ".broken-*")
        self.assertEqual(len(broken), 1)
        m._write()  # user does something -> save
        with open(broken[0], encoding="utf-8") as fh:
            self.assertIn('"uid": "a"', fh.read())

    def test_corrupt_config_restores_from_backup(self):
        self.write_cfg({"version": 1, "boxes": [box("a")]})
        self.manager()  # makes bak1
        self.write_cfg("garbage{")
        m = self.manager()
        self.assertEqual([b.uid for b in m.boxes], ["a"])
        self.assertIn("bak1", m.load_notice)
        # boxes.json is healthy again, so the next start needs no rescue
        self.assertEqual(self.read_cfg()["boxes"][0]["uid"], "a")
        m2 = self.manager()
        self.assertIsNone(m2.load_notice)
        self.assertEqual(len(glob.glob(df.CONFIG_PATH + ".broken-*")), 1)

    def test_one_bad_box_does_not_drop_the_rest(self):
        bad = box("bad", color="not-a-colour")
        self.write_cfg({"version": 1, "boxes": [box("a"), bad, box("c"), "junk"]})
        m = self.manager()
        self.assertEqual([b.uid for b in m.boxes], ["a", "c"])
        self.assertIsNotNone(m.load_notice)
        m._write()
        saved = self.read_cfg()["boxes"]
        self.assertIn(bad, saved)
        self.assertIn("junk", saved)
        self.assertEqual(len(saved), 4)

    def test_backup_rotation_skips_duplicates(self):
        for i in range(5):
            self.write_cfg({"version": 1, "boxes": [box(f"v{i}")]})
            self.manager()
            self.manager()  # identical restart: no extra rotation
        baks = sorted(glob.glob(df.CONFIG_PATH + ".bak*"))
        self.assertEqual([os.path.basename(b)[-4:] for b in baks], ["bak1", "bak2", "bak3"])
        uids = [load_json(b)["boxes"][0]["uid"] for b in baks]
        self.assertEqual(uids, ["v4", "v3", "v2"])

    def test_recover_orphaned_storage(self):
        self.write_cfg({"version": 1, "boxes": [box("owned")]})
        self.touch("appdata", "Deskfinity", "storage", "owned", "x.lnk")
        self.touch("appdata", "Deskfinity", "storage", "gone1", "y.lnk")
        self.touch("appdata", "Deskfinity", "storage", "gone1", "z.txt")
        os.makedirs(os.path.join(df.STORE_DIR, "empty"))
        m = self.manager()
        m.recover_storage()
        uids = [b.uid for b in m.boxes]
        self.assertEqual(uids, ["owned", "gone1"])
        rec = m.boxes[1]
        self.assertEqual(len(rec.items), 2)
        self.assertTrue(all(rec._in_store(p) for p in rec.items))
        m.recover_storage()  # second run finds nothing new
        self.assertEqual(len(m.boxes), 2)

    def test_unloaded_box_storage_is_not_recovered(self):
        self.write_cfg({"version": 1, "boxes": [box("bad", color=1)]})
        self.touch("appdata", "Deskfinity", "storage", "bad", "x.lnk")
        m = self.manager()
        m.recover_storage()
        self.assertEqual(m.boxes, [])


if __name__ == "__main__":
    unittest.main()
