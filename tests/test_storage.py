from test_search import catalog_of

from smallthings.catalog import Entry
from smallthings.storage import Store


def test_cache_and_journal_position_commit_together(tmp_path):
    source = catalog_of(["one.txt", "two.txt"]).sources[0]
    store = Store(tmp_path / "catalog.db")
    store.replace(source)
    loaded = store.load("volume", "D:\\")
    assert loaded.root == "D:\\"
    assert loaded.objects == source.objects
    assert loaded.links == source.links
    updates = [(10, source.objects[10], (Entry(10, 5, "renamed.txt"),)), (11, None, ())]
    updated = source.changed(updates, (1, 500))
    store.update(updated, updates)
    store.close()
    reopened = Store(tmp_path / "catalog.db")
    persisted = reopened.load("volume", "C:\\")
    assert persisted.position == (1, 500)
    assert persisted.count == 1
    assert next(iter(persisted.entries)).name == "renamed.txt"
    reopened.close()
