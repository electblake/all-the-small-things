from smallthings.index_settings import IndexSettings


def test_saved_empty_catalog_does_not_reenable_discovered_drives(tmp_path):
    path = tmp_path / "index.json"
    settings = IndexSettings(path, [("C:\\", "volume-c")])
    assert settings.entries[0]["enabled"]
    settings.save([])
    assert IndexSettings(path, [("C:\\", "volume-c")]).entries == []


def test_catalog_name_and_disabled_state_survive_restart(tmp_path):
    path = tmp_path / "index.json"
    settings = IndexSettings(path, [])
    entries = [{"root": "T:\\", "identity": "volume-t", "name": "Projects", "enabled": False}]
    settings.save(entries)
    assert IndexSettings(path, []).entries == entries
