from dataclasses import replace
from datetime import UTC, datetime
from threading import Event

import pcre2
import pytest

from smallthings.catalog import Catalog, Entry, Metadata, Source
from smallthings.search import EPOCH, Options, compile_query, search


def catalog_of(names, sizes=None):
    date = EPOCH + int(datetime(2026, 10, 22, 12, tzinfo=UTC).timestamp()) * 10_000_000
    objects = {}
    links = {}
    for identity, name in enumerate(names, 10):
        objects[identity] = Metadata(identity, False, sizes[identity - 10] if sizes else 100, date, date, date,
                                     frozenset({"archive"}))
        links[identity] = (Entry(identity, 5, name),)
    return Catalog((Source("volume", "C:\\", 5, objects, links, (1, 0)),))


def names(catalog, query, options=Options()):
    return [row.entry.name for row in search(catalog, query, options, Event()).rows]


@pytest.mark.parametrize(("query", "expected"), [
    ("red blue | green", ["red blue.txt", "red green.txt"]),
    ("<red blue> | green", ["green.txt", "red blue.txt", "red green.txt"]),
    ('"red blue"', ["red blue.txt"]),
    ("!red", ["green.txt", "REPORT.PDF"]),
    ("*.pdf", ["REPORT.PDF"]),
    ("report", ["REPORT.PDF"]),
    ("case:report", []),
    ("ext:pdf;txt !green", ["red blue.txt", "REPORT.PDF"]),
    ("regex:^REPORT\\.PDF$", ["REPORT.PDF"]),
])
def test_everything_grammar(query, expected):
    assert names(catalog_of(["red blue.txt", "red green.txt", "green.txt", "REPORT.PDF"]), query) == expected


def test_size_boundaries_and_comparison_tokens():
    catalog = catalog_of(["a", "b", "c", "d"], [1023, 1024, 2047, 2048])
    assert names(catalog, "size:1kb") == ["b", "c"]
    assert names(catalog, "size:=1kb") == ["b"]
    assert names(catalog, "size:<1024") == ["a"]
    assert names(catalog, "<size:>=1024 size:<2048>") == ["b", "c"]
    assert names(catalog, "size:1kb..2kb") == ["b", "c", "d"]


def test_pcre_specific_features_and_errors():
    catalog = catalog_of(["foobar.txt", "bar.txt"])
    assert names(catalog, r"foo\Kbar", Options(regex=True)) == ["foobar.txt"]
    with pytest.raises(pcre2.PatternError):
        compile_query("[", Options(regex=True))
    assert names(catalog, '"bar"', Options(regex=True)) == []
    with pytest.raises(StopIteration):
        compile_query('"unclosed', Options())


def test_snapshot_links_and_directory_moves():
    catalog = catalog_of(["folder", "file.txt"])
    source = catalog.sources[0]
    source = source.changed([
        (10, replace(source.objects[10], folder=True, size=None), source.links[10]),
        (11, source.objects[11], (Entry(11, 10, "file.txt"), Entry(11, 5, "other.txt"))),
    ], (1, 1))
    catalog = Catalog((source,))
    original = search(catalog, "ext:txt", Options(), Event())
    updated = source.changed([(10, source.objects[10], (Entry(10, 5, "renamed"),))], (1, 42))
    assert original.rows[0].path == "C:\\folder\\file.txt"
    result = search(Catalog((updated,)), "ext:txt", Options(), Event())
    assert result.rows[0].path == "C:\\renamed\\file.txt"
    removed = updated.changed([(11, source.objects[11], (Entry(11, 5, "other.txt"),))], (1, 43))
    assert names(Catalog((removed,)), "ext:txt") == ["other.txt"]


def test_no_result_cap_and_stable_windows():
    catalog = catalog_of([f"file-{i:05d}" for i in range(12001)])
    result = search(catalog, "", Options(), Event())
    assert result.total == 12001
    assert result.window(12000, 20)[0].entry.name == "file-12000"
    assert search(catalog, "", Options(), Event()).rows is result.rows


def test_cancellation():
    cancelled = Event()
    cancelled.set()
    assert search(catalog_of(["file"]), "file", Options(), cancelled) is None


def test_dates_and_modifiers():
    catalog = catalog_of(["file.txt", "profile.txt", "REPORT.PDF"])
    now = datetime(2026, 10, 22, 15, tzinfo=UTC)
    predicate = compile_query("dm:today", Options(), now)
    assert all(predicate(row) for row in catalog.rows())
    assert names(catalog, "wholewords:file") == ["file.txt"]
    assert names(catalog, "no-case:report", Options(case=True)) == ["REPORT.PDF"]
    assert names(catalog, "attrib:a") == ["file.txt", "profile.txt", "REPORT.PDF"]


def test_path_wildcards():
    catalog = catalog_of(["folder", "file.txt"])
    source = catalog.sources[0]
    source = source.changed([
        (10, replace(source.objects[10], folder=True, size=None), source.links[10]),
        (11, source.objects[11], (Entry(11, 10, "file.txt"),)),
    ], (1, 1))
    catalog = Catalog((source,))
    assert names(catalog, r"C:\*.txt") == []
    assert names(catalog, r"C:\**.txt") == ["file.txt"]
    assert names(catalog, "C:\\folder\\") == ["file.txt"]


def test_live_name_index_add_remove_and_metadata_changes():
    source = catalog_of(["before.txt"]).sources[0]
    renamed = source.changed([(10, source.objects[10], (Entry(10, 5, "after.txt"),))], (1, 1))
    assert names(Catalog((renamed,)), "before") == []
    assert names(Catalog((renamed,)), "after") == ["after.txt"]
    resized = renamed.changed([(10, replace(renamed.objects[10], size=300), renamed.links[10])], (1, 2))
    assert names(Catalog((resized,)), "after size:300") == ["after.txt"]
    removed = resized.changed([(10, None, ())], (1, 3))
    assert names(Catalog((removed,)), "after") == []
    assert names(Catalog((source,)), "before") == ["before.txt"]


def test_sort_absent_and_descending():
    catalog = catalog_of(["a", "b", "c"], [2, None, 1])
    assert names(catalog, "", Options(sort="size", folders_first=False)) == ["c", "a", "b"]
    assert names(catalog, "", Options(sort="size", descending=True, folders_first=False)) == ["a", "c", "b"]


def test_numeric_attributes_and_calendar_month():
    catalog = catalog_of(["a"])
    assert names(catalog, "attributes:0x20") == ["a"]
    assert names(catalog, "date-modified:10/2026") == ["a"]


@pytest.mark.parametrize("sort", ["name", "path", "size", "modified", "extension"])
@pytest.mark.parametrize("descending", [False, True])
def test_incremental_empty_order_matches_full_search(sort, descending):
    catalog = catalog_of(["a.txt", "b.pdf", "c.py", "d.txt"], [4, 3, 2, 1])
    options = Options(sort=sort, descending=descending)
    previous = search(catalog, "", options, Event())
    source = catalog.sources[0]
    changed = source.changed([
        (10, replace(source.objects[10], size=0), (Entry(10, 5, "z.txt"),)),
        (11, None, ()),
    ], (1, 1))
    changed = changed.changed([
        (12, replace(source.objects[12], modified=1), changed.links[12]),
        (20, replace(source.objects[10], identity=20), (Entry(20, 5, "new.txt"),)),
    ], (1, 2))
    updated_catalog = Catalog((changed,))
    incremental = search(updated_catalog, "", options, Event(), previous)
    full = search(updated_catalog, "file:|folder:", options, Event())
    assert [row.path for row in incremental.rows] == [row.path for row in full.rows]
    assert [row.entry.name for row in previous.rows] != [row.entry.name for row in incremental.rows]


def test_metadata_update_reuses_name_order_but_exposes_new_size():
    catalog = catalog_of(["a"])
    previous = search(catalog, "", Options(), Event())
    source = catalog.sources[0]
    updated = source.changed([(10, replace(source.objects[10], size=456), source.links[10])], (1, 1))
    result = search(Catalog((updated,)), "", Options(), Event(), previous)
    assert result.rows.references is previous.rows.references
    assert result.rows[0].metadata.size == 456
    assert previous.rows[0].metadata.size == 100


def test_directory_move_reorders_duplicate_names_in_incremental_results():
    source = catalog_of(["a", "b", "same.txt", "same.txt"]).sources[0]
    source = source.changed([
        (10, replace(source.objects[10], folder=True, size=None), source.links[10]),
        (11, replace(source.objects[11], folder=True, size=None), source.links[11]),
        (12, source.objects[12], (Entry(12, 10, "same.txt"),)),
        (13, source.objects[13], (Entry(13, 11, "same.txt"),)),
    ], (1, 1))
    previous = search(Catalog((source,)), "", Options(), Event())
    moved = source.changed([(10, source.objects[10], (Entry(10, 5, "z"),))], (1, 2))
    result = search(Catalog((moved,)), "", Options(), Event(), previous)
    assert [row.path for row in result.rows if not row.metadata.folder] == [
        "C:\\b\\same.txt", "C:\\z\\same.txt"]
    assert [row.path for row in previous.rows if not row.metadata.folder] == [
        "C:\\a\\same.txt", "C:\\b\\same.txt"]


def test_unicode_filename_index_offsets_and_casefold():
    catalog = catalog_of(["日本語.txt", "Straße.txt", "📁 report.txt", "last.txt"])
    assert names(catalog, "日本語") == ["日本語.txt"]
    assert names(catalog, "STRASSE") == ["Straße.txt"]
    assert names(catalog, "📁") == ["📁 report.txt"]
    assert names(catalog, "last") == ["last.txt"]
