import ctypes
from threading import Event

from smallthings.catalog import Catalog
from smallthings.filesystem import scan
from smallthings.search import Options, search


def test_normal_user_scan_and_refresh(tmp_path):
    assert not ctypes.windll.shell32.IsUserAnAdmin()
    root = tmp_path / 'root'
    root.mkdir()
    nested = root / 'nested'
    nested.mkdir()
    target = nested / 'report.txt'
    target.write_text('contents')
    issues = []
    source, complete = list(scan(str(root), 'test', Event(), lambda *args: issues.append(args)))[-1]
    assert complete
    assert not issues
    result = search(Catalog((source,)), 'report', Options(), Event())
    assert result.total == 1
    assert result.rows[0].path == str(target)
    assert result.rows[0].metadata.size == 8
    previous = search(Catalog((source,)), '', Options(), Event())
    target.rename(nested / 'renamed.txt')
    changed, _ = list(scan(str(root), 'test', Event(), lambda *args: issues.append(args)))[-1]
    result = search(Catalog((changed,), 1), '', Options(), Event(), previous)
    assert {row.entry.name for row in result.rows} == {'nested', 'renamed.txt'}
    (nested / 'renamed.txt').unlink()
    changed, _ = list(scan(str(root), 'test', Event(), lambda *args: issues.append(args)))[-1]
    assert search(Catalog((changed,), 2), 'renamed', Options(), Event(), result).total == 0


def test_real_access_denial_is_reported_without_elevation():
    assert not ctypes.windll.shell32.IsUserAnAdmin()
    issues = []
    source, complete = list(scan('C:\\System Volume Information', 'denied', Event(),
                                 lambda *args: issues.append(args)))[-1]
    assert complete
    assert source.count == 0
    assert len(issues) == 1
    assert 'Access is denied' in issues[0][1]


def test_inaccessible_child_does_not_stop_siblings(monkeypatch, tmp_path):
    import os
    (tmp_path / 'blocked').mkdir()
    (tmp_path / 'readable.txt').write_text('readable')
    scandir = os.scandir
    def enumerate_directory(path):
        if str(path).endswith('blocked'):
            raise PermissionError(13, 'Access is denied', path)
        return scandir(path)
    monkeypatch.setattr(os, 'scandir', enumerate_directory)
    issues = []
    source, complete = list(scan(str(tmp_path), 'test', Event(), lambda *args: issues.append(args)))[-1]
    assert complete
    assert len(issues) == 1
    assert search(Catalog((source,)), 'readable', Options(), Event()).total == 1
