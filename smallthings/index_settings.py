"""Persist the user's selected volume identities independently of cached metadata."""
import json
from pathlib import Path

from PySide6.QtCore import QSettings


class IndexSettings:
    def __init__(self, path, volumes):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.store = QSettings(str(self.path), QSettings.Format.IniFormat)
        if self.store.contains("index/roots"):
            self.entries = json.loads(self.store.value("index/roots"))
        elif self.path.with_name("index.json").exists():
            self.save(json.loads(self.path.with_name("index.json").read_text(encoding="utf-8")))
        else:
            self.entries = [{"identity": identity, "root": root, "name": root, "enabled": True}
                            for root, identity in volumes]
            self.save(self.entries)

    def save(self, entries):
        self.entries = [dict(entry) for entry in entries]
        self.store.setValue("index/roots", json.dumps(self.entries))
        self.store.sync()
