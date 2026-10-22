from dataclasses import replace
from threading import Event

from PySide6.QtCore import QModelIndex
from PySide6.QtTest import QAbstractItemModelTester
from test_search import catalog_of

from smallthings.catalog import Catalog, Entry
from smallthings.search import Options, search
from smallthings.tree_model import CatalogTreeModel


def folder_catalog():
    source = catalog_of(["Docs", "Nested", "a.txt", "b.txt", "Docs-other", "outside.txt"]).sources[0]
    return Catalog((source.changed([
        (10, replace(source.objects[10], folder=True, size=None), (Entry(10, 5, "Docs"),)),
        (11, replace(source.objects[11], folder=True, size=None), (Entry(11, 10, "Nested"),)),
        (12, source.objects[12], (Entry(12, 10, "a.txt"),)),
        (13, source.objects[13], (Entry(13, 11, "b.txt"),)),
        (14, replace(source.objects[14], folder=True, size=None), (Entry(14, 5, "Docs-other"),)),
        (15, source.objects[15], (Entry(15, 14, "outside.txt"),)),
    ], (1, 1)),))


def test_tree_hierarchy_and_live_updates():
    catalog = folder_catalog()
    model = CatalogTreeModel()
    tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Warning)
    settings = [{"identity": "volume", "root": "C:\\", "name": "Drive", "enabled": True}]
    model.publish(catalog, settings)
    drive = model.index(0, 0)
    docs = model.index(0, 0, drive)
    nested = model.index(0, 0, docs)
    assert model.data(docs) == "Docs"
    assert model.data(nested) == "Nested"
    assert model.parent(nested) == docs
    assert model.rowCount(docs) == 1
    assert model.rowCount(nested) == 0
    assert model.location(docs) == {"identity": "volume", "folder": "10"}
    source = catalog.sources[0]
    changed = source.changed([(11, source.objects[11], (Entry(11, 5, "Moved"),))], (1, 2))
    model.publish(Catalog((changed,)), settings)
    assert model.rowCount(docs) == 0
    assert model.rowCount(drive) == 3
    model.publish(Catalog(()), [])
    assert model.rowCount(QModelIndex()) == 0
    assert tester.model() is model


def test_folder_scope_includes_descendants_not_similar_prefixes():
    catalog = folder_catalog()
    options = Options(root="volume", folder="C:\\Docs")
    result = search(catalog, "", options, Event())
    assert {row.entry.name for row in result.rows} == {"Nested", "a.txt", "b.txt"}
    assert {row.entry.name for row in search(catalog, "ext:txt", options, Event()).rows} == {"a.txt", "b.txt"}
    source = catalog.sources[0]
    moved = source.changed([(11, source.objects[11], (Entry(11, 14, "Nested"),))], (1, 2))
    result = search(Catalog((moved,)), "", options, Event(), result)
    assert [row.entry.name for row in result.rows] == ["a.txt"]
    assert source.folder_children is source.changed([(12, replace(source.objects[12], size=200), source.links[12])], (1, 3)).folder_children
