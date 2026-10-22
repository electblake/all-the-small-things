"""Persist the user's selected volume identities independently of cached metadata."""
import json
from pathlib import Path


class IndexSettings:
    def __init__(self, path, volumes):
        self.path = Path(path)
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.entries = [{"identity": identity, "root": root, "name": root, "enabled": True}
                            for root, identity in volumes]
            self.save(self.entries)

    def save(self, entries):
        self.entries = [dict(entry) for entry in entries]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")
