import struct

import pytest

from smallthings.catalog import Source
from smallthings.ntfs import Volume, attribute_references, fixup, parse_object, runs


def resident(kind, value):
    length = (24 + len(value) + 7) // 8 * 8
    result = bytearray(length)
    struct.pack_into("<IIBBHHH", result, 0, kind, length, 0, 0, 0, 0, 0)
    struct.pack_into("<IH", result, 16, len(value), 24)
    result[24:24 + len(value)] = value
    return bytes(result)


def filename(name, namespace, parent=5):
    data = bytearray(66 + len(name.encode("utf-16-le")))
    struct.pack_into("<Q", data, 0, parent)
    struct.pack_into("<BB", data, 64, len(name), namespace)
    data[66:] = name.encode("utf-16-le")
    return resident(0x30, data)


def test_fixup_and_namespaces_and_shared_metadata():
    standard = struct.pack("<QQQQI", 1, 2, 3, 4, 0x22)
    attrs = resident(0x10, standard) + filename("Long name.txt", 1)
    attrs += filename("LONGNA~1.TXT", 2) + filename("another.txt", 1, 7) + resident(0x80, b"1234")
    record = bytearray(1024)
    record[:4] = b"FILE"
    struct.pack_into("<HH", record, 4, 48, 3)
    struct.pack_into("<H", record, 16, 9)
    struct.pack_into("<HH", record, 20, 56, 1)
    struct.pack_into("<I", record, 44, 123)
    record[56:56 + len(attrs)] = attrs
    struct.pack_into("<I", record, 56 + len(attrs), 0xFFFFFFFF)
    record[48:54] = b"XY" + record[510:512] + record[1022:1024]
    record[510:512] = record[1022:1024] = b"XY"
    metadata, links = parse_object(fixup(record, 512))
    assert metadata.identity == 123 | (9 << 48)
    assert metadata.size == 4
    assert metadata.modified == 2
    assert metadata.attributes == frozenset({"hidden", "archive"})
    assert [link.name for link in links] == ["Long name.txt", "another.txt"]
    assert links[1].parent_id == 7


def test_fragmented_signed_runs_and_sparse_extent():
    encoded = bytes([0x11, 3, 20, 0x11, 2, 0xFC, 0x01, 5, 0])
    assert list(runs(encoded)) == [(0, 3, 20), (3, 2, 16), (5, 5, None)]


def test_attribute_extension_reference():
    entry = bytearray(32)
    struct.pack_into("<IH", entry, 0, 0x80, 32)
    struct.pack_into("<Q", entry, 16, 765 | (3 << 48))
    assert list(attribute_references(entry)) == [765 | (3 << 48)]


def test_idle_journal_reads_still_validate_native_cursor():
    volume = object.__new__(Volume)
    volume.journal_position = lambda: (1, 50)
    requests = []
    def read(code, request, capacity):
        requests.append(request)
        return struct.pack("<q", 50)
    volume.ioctl = read
    source = Source("volume", "C:\\", 5, {}, {}, (1, 50))
    assert volume.changes(source) is source
    assert len(requests) == 1
    failure = OSError("native journal failure")
    def fail(code, request, capacity):
        raise failure
    volume.ioctl = fail
    with pytest.raises(OSError) as caught:
        volume.changes(source)
    assert caught.value is failure
