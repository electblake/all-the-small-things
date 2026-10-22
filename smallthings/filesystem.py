"""Ordinary, non-elevated directory enumeration for local and network roots."""
import hashlib
import ntpath
import os
import stat
from collections import deque
from time import monotonic

from .catalog import Entry, Metadata, Source
from .ntfs import attribute_names
from .search import EPOCH


def path_id(path):
    return int.from_bytes(hashlib.blake2b(ntpath.normcase(path).encode('utf-8'), digest_size=8).digest(), 'little')


def scan(root, identity, stopped, report):
    root = ntpath.join(root, '')
    root_id = path_id(root)
    source = Source(identity, root, root_id, {}, {}, (0, 0))
    pending = deque([(root, root_id)])
    updates = []
    last_publish = monotonic()
    while pending and not stopped.is_set():
        path, parent = pending.popleft()
        try:
            with os.scandir(path) as entries:
                for item in entries:
                    if stopped.is_set():
                        return
                    try:
                        info = item.stat(follow_symlinks=False)
                    except OSError as error:
                        report(item.path, str(error))
                        continue
                    number = path_id(item.path)
                    folder = bool(info.st_file_attributes & 0x10)
                    metadata = Metadata(number, folder, None if folder else info.st_size,
                                        EPOCH + info.st_birthtime_ns // 100,
                                        EPOCH + info.st_mtime_ns // 100,
                                        EPOCH + info.st_atime_ns // 100,
                                        attribute_names(info.st_file_attributes))
                    updates.append((number, metadata, (Entry(number, parent, item.name),)))
                    if folder:
                        # Enumerate links themselves, not their targets: avoids cycles and crossing roots.
                        if info.st_reparse_tag in (stat.IO_REPARSE_TAG_SYMLINK, stat.IO_REPARSE_TAG_MOUNT_POINT):
                            report(item.path, 'Directory link indexed; target is not traversed.')
                        else:
                            pending.append((item.path, number))
        except OSError as error:
            report(path, str(error))
        if updates and (len(updates) >= 8192 or monotonic() - last_publish >= 1):
            source = source.changed(updates, (0, 0))
            updates = []
            last_publish = monotonic()
            yield source, False
    if stopped.is_set():
        return
    source = source.changed(updates, (0, 0))
    # Compact the filename index once the scan is complete.
    yield Source(identity, root, root_id, source.objects, source.links, (0, 0)), True
