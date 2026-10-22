import ntpath
from array import array
from bisect import bisect_right
from dataclasses import dataclass, field
from itertools import chain

from immutables import Map


class NameIndex:
    def __init__(self, entries):
        self.entries = tuple(entries)
        self.offsets = array("Q")
        offset = 0
        for entry in self.entries:
            self.offsets.append(offset)
            offset += len(entry.key.encode("utf-8")) + 1
        self.text = b"\0".join(entry.key.encode("utf-8") for entry in self.entries)

    def candidates(self, needle, cancelled):
        needle = needle.encode("utf-8")
        offset = self.text.find(needle)
        while offset >= 0 and not cancelled.is_set():
            index = bisect_right(self.offsets, offset) - 1
            yield self.entries[index]
            end = self.offsets[index + 1] if index + 1 < len(self.entries) else len(self.text)
            offset = self.text.find(needle, end)


@dataclass(frozen=True, slots=True)
class Metadata:
    identity: int
    folder: bool
    size: int | None
    created: int | None
    modified: int | None
    accessed: int | None
    attributes: frozenset[str]


@dataclass(frozen=True, slots=True)
class Entry:
    object_id: int
    parent_id: int
    name: str
    key: str = field(init=False)

    def __post_init__(self):
        key = self.name.casefold()
        object.__setattr__(self, "key", self.name if key == self.name else key)

    @property
    def identity(self):
        return self.object_id, self.parent_id, self.name

    @property
    def extension(self):
        return ntpath.splitext(self.name)[1][1:]


@dataclass
class Source:
    identity: str
    root: str
    root_id: int
    objects: dict[int, Metadata]
    links: dict[int, tuple[Entry, ...]]
    position: tuple[int, int]
    count: int = field(init=False)
    name_index: NameIndex = field(init=False)
    additions: Map = field(init=False)
    version: int = field(init=False, default=0)
    revisions: Map = field(init=False)
    folder_children: Map = field(init=False)

    def __post_init__(self):
        self.objects = Map(self.objects)
        self.links = Map(self.links)
        self.count = sum(map(len, self.links.values()))
        self.name_index = NameIndex(self.entries)
        self.additions = Map()
        self.version = 0
        self.revisions = Map()
        folders = {}
        for identity, metadata in self.objects.items():
            if metadata.folder:
                for entry in self.links.get(identity, ()):
                    folders.setdefault(entry.parent_id, []).append(entry)
        self.folder_children = Map({parent: tuple(sorted(entries, key=lambda e: (e.key, e.identity)))
                                    for parent, entries in folders.items()})

    @property
    def entries(self):
        return chain.from_iterable(self.links.values())

    def path(self, entry: Entry):
        names = [entry.name]
        parent = entry.parent_id
        while parent != self.root_id:
            directory = self.links[parent][0]
            names.append(directory.name)
            parent = directory.parent_id
        return self.root + "\\".join(reversed(names))

    def changed(self, updates, position):
        objects = self.objects.mutate()
        links = self.links.mutate()
        additions = self.additions.mutate()
        revisions = self.revisions.mutate()
        count = self.count
        folders = self.folder_children.mutate()
        folders_changed = False
        for identity, metadata, entries in updates:
            revisions[identity] = self.version + 1
            if identity in links:
                count -= len(links[identity])
                previous = links[identity]
            else:
                previous = ()
            old_folders = previous if identity in self.objects and self.objects[identity].folder else ()
            new_folders = entries if metadata is not None and metadata.folder else ()
            if old_folders != new_folders:
                folders_changed = True
                for entry in old_folders:
                    folders[entry.parent_id] = tuple(e for e in folders[entry.parent_id] if e != entry)
                for entry in new_folders:
                    siblings = folders.get(entry.parent_id, ()) + (entry,)
                    folders[entry.parent_id] = tuple(sorted(siblings, key=lambda e: (e.key, e.identity)))
            for entry in previous:
                additions.pop(entry.identity, None)
            if metadata is None:
                objects.pop(identity, None)
                links.pop(identity, None)
            else:
                objects[identity] = metadata
                links[identity] = entries
                count += len(entries)
                for entry in entries:
                    if entry not in previous or entry.identity in self.additions:
                        additions[entry.identity] = entry
        source = object.__new__(Source)
        source.identity, source.root, source.root_id = self.identity, self.root, self.root_id
        source.objects, source.links = objects.finish(), links.finish()
        source.position, source.count = position, count
        source.name_index, source.additions = self.name_index, additions.finish()
        source.version, source.revisions = self.version + 1, revisions.finish()
        source.folder_children = folders.finish() if folders_changed else self.folder_children
        return source

    def matching_names(self, needle, cancelled):
        emitted = set()
        for entry in self.name_index.candidates(needle, cancelled):
            if entry in self.links.get(entry.object_id, ()):
                emitted.add(entry.identity)
                yield entry
        for entry in self.additions.values():
            if entry.identity not in emitted and needle in entry.key:
                yield entry


@dataclass(frozen=True, slots=True)
class Row:
    source: Source
    entry: Entry

    @property
    def metadata(self):
        return self.source.objects[self.entry.object_id]

    @property
    def path(self):
        return self.source.path(self.entry)


@dataclass
class Catalog:
    sources: tuple[Source, ...]
    generation: int = 0
    orders: dict = field(default_factory=dict)

    @property
    def count(self):
        return sum(source.count for source in self.sources)

    def rows(self):
        for source in self.sources:
            for entry in source.entries:
                yield Row(source, entry)
