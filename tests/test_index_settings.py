import json

import pytest

from smallthings.index_settings import IndexSettings


def test_saved_empty_catalog_does_not_reenable_discovered_drives(tmp_path):
    path = tmp_path / "settings.ini"
    settings = IndexSettings(path, [("C:\\", "volume-c")])
    assert settings.entries[0]["enabled"]
    settings.save([])
    assert IndexSettings(path, [("C:\\", "volume-c")]).entries == []


def test_catalog_name_and_disabled_state_survive_restart(tmp_path):
    path = tmp_path / "settings.ini"
    settings = IndexSettings(path, [])
    entries = [{"root": "T:\\", "identity": "volume-t", "name": "Projects", "enabled": False}]
    settings.save(entries)
    assert IndexSettings(path, []).entries == entries


@pytest.mark.parametrize("entries", [[], [
    {"root": "T:\\", "identity": "volume-t", "name": "Projects", "enabled": False},
]])
def test_legacy_catalog_migrates_once(tmp_path, entries):
    legacy = tmp_path / "index.json"
    legacy.write_text(json.dumps(entries), encoding="utf-8")
    path = tmp_path / "settings.ini"
    settings = IndexSettings(path, [("C:\\", "volume-c")])
    assert settings.entries == entries
    settings.save([])
    legacy.write_text("invalid JSON", encoding="utf-8")
    assert IndexSettings(path, [("C:\\", "volume-c")]).entries == []


def test_invalid_legacy_catalog_surfaces_parse_failure(tmp_path):
    (tmp_path / "index.json").write_text("invalid JSON", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        IndexSettings(tmp_path / "settings.ini", [])
