"""Read-only NTFS MFT enumeration and USN journal maintenance."""
import ctypes
import struct
from ctypes import wintypes as w
from dataclasses import dataclass
from functools import lru_cache

from .catalog import Entry, Metadata, Source

MASK48 = (1 << 48) - 1
ATTRIBUTE_NAMES = {
    0x1: "readonly", 0x2: "hidden", 0x4: "system", 0x10: "directory", 0x20: "archive",
    0x80: "normal", 0x100: "temporary", 0x200: "sparse", 0x400: "reparse",
    0x800: "compressed", 0x1000: "offline", 0x2000: "not_content_indexed", 0x4000: "encrypted",
    0x8000: "integrity", 0x20000: "no_scrub", 0x80000: "pinned", 0x100000: "unpinned",
    0x400000: "recall",
}


@lru_cache(maxsize=512)
def attribute_names(flags):
    return frozenset(name for bit, name in ATTRIBUTE_NAMES.items() if flags & bit)


def native_result(result, function, arguments):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return result


class Windows:
    def __init__(self):
        self.dll = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateFileW": (w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]),
            "CloseHandle": (w.BOOL, [w.HANDLE]),
            "DeviceIoControl": (w.BOOL, [w.HANDLE, w.DWORD, w.LPVOID, w.DWORD, w.LPVOID,
                                        w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]),
            "SetFilePointerEx": (w.BOOL, [w.HANDLE, ctypes.c_int64, ctypes.POINTER(ctypes.c_int64), w.DWORD]),
            "ReadFile": (w.BOOL, [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]),
            "GetLogicalDrives": (w.DWORD, []),
            "GetDriveTypeW": (w.UINT, [w.LPCWSTR]),
            "GetVolumeInformationW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, w.DWORD, ctypes.POINTER(w.DWORD),
                                               ctypes.POINTER(w.DWORD), ctypes.POINTER(w.DWORD),
                                               w.LPWSTR, w.DWORD]),
            "GetVolumeNameForVolumeMountPointW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, w.DWORD]),
        }
        for name, (restype, argtypes) in signatures.items():
            function = getattr(self.dll, name)
            function.restype, function.argtypes = restype, argtypes
            if restype == w.BOOL:
                function.errcheck = native_result

    def drives(self):
        from PySide6.QtCore import QStorageInfo

        mask = self.dll.GetLogicalDrives()
        for number in range(26):
            if not mask & (1 << number):
                continue
            root = chr(65 + number) + ":\\"
            kind = self.dll.GetDriveTypeW(root)
            storage = QStorageInfo(root)
            filesystem = bytes(storage.fileSystemType()).decode()
            supported = kind in (2, 3, 4, 5)
            identity = root.casefold()
            if kind in (2, 3) and storage.isReady():
                buffer = ctypes.create_unicode_buffer(64)
                self.dll.GetVolumeNameForVolumeMountPointW(root, buffer, 64)
                identity = buffer.value
            yield {"root": root, "identity": identity, "name": root,
                       "filesystem": filesystem, "network": kind == 4, "supported": supported}

    def volumes(self):
        for drive in self.drives():
            yield drive["root"], drive["identity"]


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def u64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]


def fixup(record, sector_size):
    data = bytearray(record)
    offset, count = struct.unpack_from("<HH", data, 4)
    sector_size = len(data) // (count - 1)
    for index in range(1, count):
        end = index * sector_size
        data[end - 2:end] = data[offset + index * 2:offset + index * 2 + 2]
    return bytes(data)


@dataclass(frozen=True)
class Attribute:
    kind: int
    name: str
    resident: bool
    data: bytes
    size: int
    vcn: int


def attributes(record):
    offset = u16(record, 20)
    while u32(record, offset) != 0xFFFFFFFF:
        kind, length = struct.unpack_from("<II", record, offset)
        nonresident, name_length = struct.unpack_from("<BB", record, offset + 8)
        name_offset = u16(record, offset + 10)
        name = record[offset + name_offset:offset + name_offset + name_length * 2].decode("utf-16-le")
        if nonresident:
            run_offset = u16(record, offset + 32)
            yield Attribute(kind, name, False, record[offset + run_offset:offset + length],
                            u64(record, offset + 48), u64(record, offset + 16))
        else:
            size = u32(record, offset + 16)
            start = offset + u16(record, offset + 20)
            yield Attribute(kind, name, True, record[start:start + size], size, 0)
        offset += length


def runs(data, start_vcn=0):
    position, lcn, vcn = 0, 0, start_vcn
    while data[position]:
        header = data[position]
        length_bytes, offset_bytes = header & 15, header >> 4
        position += 1
        count = int.from_bytes(data[position:position + length_bytes], "little")
        position += length_bytes
        delta = int.from_bytes(data[position:position + offset_bytes], "little", signed=True)
        position += offset_bytes
        lcn += delta
        yield vcn, count, lcn if offset_bytes else None
        vcn += count


def attribute_references(data):
    offset = 0
    while offset < len(data) and u32(data, offset) != 0xFFFFFFFF:
        yield u64(data, offset + 16)
        offset += u16(data, offset + 4)


def parse_object(record, extra=()):
    number = u32(record, 44)
    identity = number | (u16(record, 16) << 48)
    folder = bool(u16(record, 22) & 2)
    attrs = list(attributes(record)) + list(extra)
    standard = next(attr.data for attr in attrs if attr.kind == 0x10)
    created, modified, _, accessed = struct.unpack_from("<QQQQ", standard)
    flags = u32(standard, 32)
    size = None
    if not folder:
        for attr in attrs:
            if attr.kind == 0x80 and not attr.name and attr.vcn == 0:
                size = attr.size
    metadata = Metadata(identity, folder, size, created, modified, accessed,
                        attribute_names(flags))
    entries = []
    for attr in attrs:
        if attr.kind == 0x30:
            length, namespace = struct.unpack_from("<BB", attr.data, 64)
            if namespace == 2:
                continue
            name = attr.data[66:66 + length * 2].decode("utf-16-le")
            entries.append(Entry(identity, u64(attr.data, 0), name))
    return metadata, tuple(dict.fromkeys(entries))


class Volume:
    def __init__(self, root, identity):
        self.api = Windows().dll
        self.root, self.identity = root, identity
        self.handle = self.api.CreateFileW(identity.rstrip("\\"), 0x80000000, 7, None, 3, 0, None)
        if self.handle == w.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        geometry = self.ioctl(0x90064, b"", 128)
        self.sector_size, self.cluster_size, self.record_size = struct.unpack_from("<III", geometry, 40)
        self.mft_length = u64(geometry, 56)
        self.mft_lcn = u64(geometry, 64)
        self.refresh_mapping()

    def close(self):
        self.api.CloseHandle(self.handle)

    def ioctl(self, code, data, capacity):
        output = ctypes.create_string_buffer(capacity)
        count = w.DWORD()
        self.api.DeviceIoControl(self.handle, code, data, len(data), output, capacity,
                                 ctypes.byref(count), None)
        return output.raw[:count.value]

    def read(self, offset, length):
        aligned_offset = offset // self.sector_size * self.sector_size
        prefix = offset - aligned_offset
        aligned_length = (prefix + length + self.sector_size - 1) // self.sector_size * self.sector_size
        self.api.SetFilePointerEx(self.handle, aligned_offset, None, 0)
        buffer = ctypes.create_string_buffer(aligned_length)
        count = w.DWORD()
        self.api.ReadFile(self.handle, buffer, aligned_length, ctypes.byref(count), None)
        return buffer.raw[prefix:min(prefix + length, count.value)]

    def attribute_data(self, attr):
        if attr.resident:
            return attr.data
        return b"".join(self.read(lcn * self.cluster_size, count * self.cluster_size)
                        for _, count, lcn in runs(attr.data, attr.vcn))[:attr.size]

    def kernel_record(self, reference):
        output = self.ioctl(0x90068, struct.pack("<Q", reference & MASK48), self.record_size + 16)
        # FSCTL_GET_NTFS_FILE_RECORD returns the nearest in-use record at or below the requested slot.
        if u64(output, 0) & MASK48 != reference & MASK48:
            return None
        return output[12:12 + u32(output, 8)]

    def extended_attributes(self, record):
        attrs = list(attributes(record))
        references = set()
        for attr in attrs:
            if attr.kind == 0x20:
                references.update(attribute_references(self.attribute_data(attr)))
        own = u32(record, 44) | (u16(record, 16) << 48)
        for reference in sorted(references - {own}):
            extension = self.kernel_record(reference)
            attrs.extend(attributes(extension))
        return attrs

    def refresh_mapping(self):
        record = fixup(self.read(self.mft_lcn * self.cluster_size, self.record_size), self.sector_size)
        attrs = self.extended_attributes(record)
        data_attrs = [attr for attr in attrs if attr.kind == 0x80 and not attr.name]
        self.mft_runs = sorted(run for attr in data_attrs for run in runs(attr.data, attr.vcn))
        self.mft_length = next(attr.size for attr in data_attrs if attr.vcn == 0)

    def journal_position(self):
        data = self.ioctl(0x900F4, b"", 128)
        return u64(data, 0), u64(data, 16)

    def enumerate(self, progress, stopped):
        position = self.journal_position()
        objects, links = {}, {}
        processed = 0
        root_id = None
        for vcn, clusters, lcn in self.mft_runs:
            logical = vcn * self.cluster_size
            length = min(clusters * self.cluster_size, self.mft_length - logical)
            for offset in range(0, length, 4 * 1024 * 1024):
                if stopped.is_set():
                    return None
                block = self.read(lcn * self.cluster_size + offset, min(4 * 1024 * 1024, length - offset))
                for start in range(0, len(block), self.record_size):
                    raw = block[start:start + self.record_size]
                    if raw[:4] != b"FILE" or not u16(raw, 22) & 1 or u64(raw, 32):
                        continue
                    record = fixup(raw, self.sector_size)
                    base_attrs = list(attributes(record))
                    extra = []
                    if any(attr.kind == 0x20 for attr in base_attrs):
                        extra = self.extended_attributes(record)[len(base_attrs):]
                    metadata, entries = parse_object(record, extra)
                    objects[metadata.identity] = metadata
                    if u32(record, 44) == 5:
                        root_id = metadata.identity
                    else:
                        links[metadata.identity] = entries
                    processed += 1
                if progress is not None:
                    progress(self.root, "Reading MFT", processed,
                         min(1.0, (logical + offset + len(block)) / self.mft_length))
        source = Source(self.identity, self.root, root_id, objects, links, position)
        if progress is not None:
            progress(self.root, "Applying journal", processed, 1.0)
        return self.changes(source)

    def changes(self, source, store=None):
        journal_id, start = source.position
        target = self.journal_position()[1]
        references = set()
        while True:
            request = struct.pack("<qIIQQQHHI", start, 0xFFFFFFFF, 0, 0, 0, journal_id, 2, 2, 0)
            data = self.ioctl(0x900BB, request, 1024 * 1024)
            start = struct.unpack_from("<q", data)[0]
            offset = 8
            while offset < len(data):
                length = u32(data, offset)
                references.add(u64(data, offset + 8))
                offset += length
            if start >= target:
                break
        if not references and start == source.position[1]:
            return source
        updates = []
        for reference in references:
            record = self.kernel_record(reference)
            if record is None or u16(record, 16) != reference >> 48:
                updates.append((reference, None, ()))
                continue
            if u64(record, 32):
                reference = u64(record, 32)
                record = self.kernel_record(reference)
            attrs = list(attributes(record))
            extra = self.extended_attributes(record)[len(attrs):] if any(a.kind == 0x20 for a in attrs) else []
            metadata, entries = parse_object(record, extra)
            if metadata.identity == source.root_id:
                entries = ()
            updates.append((metadata.identity, metadata, entries))
        known = {identity for identity, metadata, _ in updates if metadata is not None}
        known.add(source.root_id)
        removed = {identity for identity, metadata, _ in updates if metadata is None}
        cursor = 0
        while cursor < len(updates):
            for entry in updates[cursor][2]:
                if entry.parent_id not in known and (entry.parent_id not in source.links or entry.parent_id in removed):
                    record = self.kernel_record(entry.parent_id)
                    attrs = list(attributes(record))
                    extra = self.extended_attributes(record)[len(attrs):] if any(a.kind == 0x20 for a in attrs) else []
                    metadata, entries = parse_object(record, extra)
                    updates.append((metadata.identity, metadata, entries))
                    known.add(metadata.identity)
            cursor += 1
        updated = source.changed(updates, (journal_id, start))
        if store is not None:
            store.update(updated, updates)
        return updated
