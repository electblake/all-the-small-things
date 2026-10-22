"""Persistent metadata cache; USN positions are committed with their records."""
import sqlite3
from functools import lru_cache

from .catalog import Entry, Metadata, Source


def reference(value):
    return value.to_bytes(8, "little")


@lru_cache(maxsize=512)
def attribute_set(text):
    return frozenset(filter(None, text.split(",")))


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;
            CREATE TABLE IF NOT EXISTS source (
                identity TEXT PRIMARY KEY, root TEXT, root_id BLOB, journal BLOB, position INTEGER
            );
            CREATE TABLE IF NOT EXISTS objects (
                source TEXT, identity BLOB, folder INTEGER, size INTEGER,
                created INTEGER, modified INTEGER, accessed INTEGER, attributes TEXT,
                PRIMARY KEY (source, identity)
            ) WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS links (
                source TEXT, object BLOB, parent BLOB, name TEXT,
                PRIMARY KEY (source, object, parent, name)
            ) WITHOUT ROWID;
        """)

    def contains(self, identity):
        return self.db.execute("SELECT 1 FROM source WHERE identity=?", (identity,)).fetchone() is not None

    def load(self, identity, root, progress=None):
        root_id, journal, position = self.db.execute(
            "SELECT root_id,journal,position FROM source WHERE identity=?", (identity,)).fetchone()
        objects = {}
        object_count = self.db.execute("SELECT count(*) FROM objects WHERE source=?", (identity,)).fetchone()[0]
        link_count = self.db.execute("SELECT count(*) FROM links WHERE source=?", (identity,)).fetchone()[0]
        for index, record in enumerate(self.db.execute("SELECT identity,folder,size,created,modified,accessed,attributes FROM objects WHERE source=?", (identity,))):
            key, folder, size, created, modified, accessed, attrs = record
            number = int.from_bytes(key, "little")
            objects[number] = Metadata(number, bool(folder), size, created, modified, accessed,
                                       attribute_set(attrs))
            if progress is not None and index % 65536 == 0:
                progress(root, "Loading catalog", index, index / (object_count + link_count))
        links = {}
        for index, (key, parent, name) in enumerate(self.db.execute("SELECT object,parent,name FROM links WHERE source=?", (identity,))):
            number = int.from_bytes(key, "little")
            links.setdefault(number, []).append(Entry(number, int.from_bytes(parent, "little"), name))
            if progress is not None and index % 65536 == 0:
                progress(root, "Loading catalog", index, (object_count + index) / (object_count + link_count))
        return Source(identity, root, int.from_bytes(root_id, "little"), objects,
                      {key: tuple(value) for key, value in links.items()},
                      (int.from_bytes(journal, "little"), position))

    def replace(self, source):
        self.db.execute("DELETE FROM links WHERE source=?", (source.identity,))
        self.db.execute("DELETE FROM objects WHERE source=?", (source.identity,))
        ordered_objects = (source.objects[key] for key in sorted(source.objects, key=reference))
        self.db.executemany("INSERT INTO objects VALUES (?,?,?,?,?,?,?,?)", (
            (source.identity, reference(obj.identity), obj.folder, obj.size, obj.created, obj.modified,
             obj.accessed, ",".join(sorted(obj.attributes))) for obj in ordered_objects))
        ordered_entries = (entry for key in sorted(source.links, key=reference)
                           for entry in sorted(source.links[key], key=lambda item: (reference(item.parent_id), item.name)))
        self.db.executemany("INSERT INTO links VALUES (?,?,?,?)", (
            (source.identity, reference(entry.object_id), reference(entry.parent_id), entry.name)
            for entry in ordered_entries))
        self.commit_position(source)

    def update(self, source, updates):
        for identity, metadata, entries in updates:
            key = reference(identity)
            self.db.execute("DELETE FROM links WHERE source=? AND object=?", (source.identity, key))
            if metadata is None:
                self.db.execute("DELETE FROM objects WHERE source=? AND identity=?", (source.identity, key))
            else:
                obj = metadata
                self.db.execute("INSERT OR REPLACE INTO objects VALUES (?,?,?,?,?,?,?,?)",
                                (source.identity, key, obj.folder, obj.size, obj.created, obj.modified,
                                 obj.accessed, ",".join(sorted(obj.attributes))))
                self.db.executemany("INSERT INTO links VALUES (?,?,?,?)", (
                    (source.identity, key, reference(entry.parent_id), entry.name) for entry in entries))
        self.commit_position(source)

    def commit_position(self, source):
        self.db.execute("INSERT OR REPLACE INTO source VALUES (?,?,?,?,?)",
                        (source.identity, source.root, reference(source.root_id),
                         reference(source.position[0]), source.position[1]))
        self.db.commit()

    def close(self):
        self.db.close()
