import os
from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
from queue import SimpleQueue
from time import monotonic, sleep

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"

from PySide6.QtCore import QMetaObject, Qt, QUrl, qInstallMessageHandler
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from test_search import catalog_of

from smallthings.backend import Backend
from smallthings.catalog import Entry
from smallthings.ntfs import Windows


def test_index_failure_stops_polling(monkeypatch, tmp_path):
    app = QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(Windows, "volumes", lambda self: iter(()))
    backend = Backend()
    backend.stopped.set()
    backend.rescan.set()
    backend.index_future.result(timeout=5)
    failure = PermissionError("raw volume access denied")
    failed = Future()
    failed.set_exception(failure)
    original = backend.index_future
    backend.index_future = failed
    with pytest.raises(PermissionError) as raised:
        backend.poll()
    assert raised.value is failure
    assert not backend.timer.isActive()
    backend.index_future = original
    backend.shutdown()
    app.processEvents()


def test_query_failure_is_consumed_and_next_query_works(monkeypatch, tmp_path):
    app = QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(Windows, "volumes", lambda self: iter(()))
    backend = Backend()
    backend.timer.stop()
    backend.catalog = catalog_of(["report.pdf", "notes.txt"])
    backend._busy = False
    backend.events = SimpleQueue()
    failed = Future()
    failure = ValueError("invalid query")
    failed.set_exception(failure)
    backend.query_future = failed
    with pytest.raises(ValueError) as raised:
        backend.poll()
    assert raised.value is failure
    assert backend.query_future is None
    backend.setQuery("report")
    backend.poll()
    backend.query_future.result(timeout=5)
    backend.poll()
    assert [row.entry.name for row in backend.model.results.rows] == ["report.pdf"]
    backend.shutdown()
    app.processEvents()


def test_qml_search_sort_and_clipboard(monkeypatch, tmp_path):
    QQuickStyle.setStyle("Fusion")
    app = QGuiApplication.instance() or QGuiApplication([])
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    monkeypatch.setattr(Windows, "volumes", lambda self: iter(()))
    monkeypatch.setattr(Windows, "drives", lambda self: iter([
        {"root": "T:\\", "identity": "test-volume", "name": "Test drive", "filesystem": "NTFS", "network": False, "supported": True},
        {"root": "N:\\", "identity": "", "name": "Network", "filesystem": "NTFS", "network": True, "supported": False},
    ]))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "smallthings/qml/Main.qml")))
    assert len(engine.rootObjects()) == 1, messages
    window = engine.rootObjects()[0]
    backend.events.put(("catalog", catalog_of(["report.pdf", "notes.txt", "photo.png"]).sources))
    QTest.qWait(500)
    assert backend.resultCount == 3
    from PySide6.QtCore import QObject
    search_field = window.findChild(QObject, "searchField")
    search_field.setProperty("text", "ext:pdf")
    QTest.qWait(300)
    assert backend.resultCount == 1
    backend.copyPath(0)
    assert app.clipboard().text() == "C:\\report.pdf"
    search_field.setProperty("text", "")
    backend.sortBy(0)
    QTest.qWait(300)
    assert backend.model.results.rows[0].entry.name == "report.pdf"
    QTest.keyClick(window, Qt.Key.Key_Down)
    QTest.qWait(100)
    opened = []
    monkeypatch.setattr("os.startfile", opened.append)
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert opened == ["C:\\report.pdf"]
    open_action = window.findChild(QObject, "openAction")
    reveal_action = window.findChild(QObject, "revealAction")
    copy_action = window.findChild(QObject, "copyAction")
    assert QMetaObject.invokeMethod(open_action, "trigger")
    assert opened == ["C:\\report.pdf", "C:\\report.pdf"]
    revealed = []
    monkeypatch.setattr("subprocess.Popen", revealed.append)
    assert QMetaObject.invokeMethod(reveal_action, "trigger")
    assert revealed == [["explorer.exe", "/select,", "C:\\report.pdf"]]
    app.clipboard().clear()
    assert QMetaObject.invokeMethod(copy_action, "trigger")
    assert app.clipboard().text() == "C:\\report.pdf"
    assert backend.model.columnCount() == 5
    QTest.keyClick(window, Qt.Key.Key_Down)
    table = window.findChild(QObject, "resultsTable")
    selection = table.property("selectionModel")
    selected_name = backend.model.results.rows[selection.currentIndex().row()].entry.name
    source = backend.catalog.sources[0]
    updated = source.changed([(10, replace(source.objects[10], size=999), source.links[10])], (1, 1))
    backend.events.put(("catalog", (updated,)))
    QTest.qWait(300)
    assert backend.model.results.rows[selection.currentIndex().row()].entry.name == selected_name
    QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert search_field.property("activeFocus")
    QTest.keyClick(window, Qt.Key.Key_F1)
    QTest.qWait(100)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.qWait(100)
    Path("artifacts").mkdir(exist_ok=True)
    assert window.grabWindow().save("artifacts/ui.png")
    window.setWidth(1600)
    QTest.qWait(100)
    assert abs(table.property("contentWidth") - table.property("width")) <= 1
    window.setWidth(720)
    window.setHeight(480)
    font = window.property("font")
    font.setPointSize(18)
    window.setProperty("font", font)
    QTest.qWait(100)
    assert window.grabWindow().save("artifacts/ui-large-text.png")
    assert table.property("contentWidth") > table.property("width")
    table.setProperty("contentX", table.property("contentWidth") - table.property("width"))
    QTest.qWait(100)
    assert window.grabWindow().save("artifacts/ui-scrolled.png")
    search_field.setProperty("text", "missing-name")
    QTest.qWait(200)
    assert backend.resultCount == 0
    assert not selection.currentIndex().isValid()
    empty = window.findChild(QObject, "emptyState")
    assert empty.property("visible")
    assert empty.property("text") == "No results"
    assert empty.property("x") >= 0
    assert empty.property("y") > 0
    assert empty.property("y") + empty.property("height") < table.property("height")
    backend._busy = True
    backend.changed.emit()
    QTest.qWait(100)
    assert not empty.property("visible")
    assert window.findChild(QObject, "activityIndicator").property("running")
    assert empty.property("y") > 0
    backend._busy = False
    backend.changed.emit()
    palette = QPalette(app.palette())
    for role, color in [(QPalette.Window, "#202020"), (QPalette.Base, "#292929"),
                        (QPalette.AlternateBase, "#333333"), (QPalette.Text, "#eeeeee"),
                        (QPalette.WindowText, "#eeeeee"), (QPalette.Button, "#383838"),
                        (QPalette.ButtonText, "#eeeeee")]:
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    QTest.qWait(100)
    assert window.grabWindow().save("artifacts/ui-empty-dark.png")
    QTest.keyClick(window, Qt.Key.Key_F1)
    QTest.qWait(100)
    assert window.grabWindow().save("artifacts/ui-help-large.png")
    QTest.keyClick(window, Qt.Key.Key_Escape)
    search_field.setProperty("text", "report.pdf")
    QTest.qWait(200)
    assert backend.resultCount == 1
    deleted = updated.changed([(10, None, ())], (1, 2))
    backend.events.put(("catalog", (deleted,)))
    QTest.qWait(300)
    assert backend.resultCount == 0
    assert not selection.currentIndex().isValid()
    assert not open_action.property("enabled")
    assert not reveal_action.property("enabled")
    assert not copy_action.property("enabled")
    # Live create, rename, and delete traverse the worker search and QML model.
    created = deleted.changed([(10, updated.objects[10], (Entry(10, 5, "report.pdf"),))], (1, 3))
    backend.events.put(("catalog", (created,)))
    QTest.qWait(300)
    assert backend.resultCount == 1
    assert open_action.property("enabled")
    renamed = created.changed([(10, created.objects[10], (Entry(10, 5, "renamed.pdf"),))], (1, 4))
    backend.events.put(("catalog", (renamed,)))
    QTest.qWait(300)
    assert backend.resultCount == 0
    search_field.setProperty("text", "renamed.pdf")
    QTest.qWait(300)
    assert backend.resultCount == 1
    assert QMetaObject.invokeMethod(copy_action, "trigger")
    assert app.clipboard().text() == "C:\\renamed.pdf"
    backend.events.put(("catalog", (renamed.changed([(10, None, ())], (1, 5)),)))
    QTest.qWait(300)
    assert backend.resultCount == 0
    assert not window.findChild(QObject, "activityIndicator").property("running")
    # Editing is a draft until Save; disabled roots persist without opening a volume.
    assert QMetaObject.invokeMethod(window.findChild(QObject, "searchIndexAction"), "trigger")
    QTest.qWait(100)
    dialog = window.findChild(QObject, "searchIndexDialog")
    assert dialog.property("visible")
    add_drive = window.findChild(QObject, "addDrive")
    assert add_drive.property("enabled")
    assert QMetaObject.invokeMethod(add_drive, "click")
    QTest.qWait(50)
    assert not add_drive.property("enabled")
    assert QMetaObject.invokeMethod(window.findChild(QObject, "rootEnabled"), "toggle")
    # toggle() changes state; the user-facing toggled signal commits the draft field.
    assert QMetaObject.invokeMethod(window.findChild(QObject, "rootEnabled"), "toggled")
    assert window.grabWindow().save("artifacts/ui-search-index.png")
    assert QMetaObject.invokeMethod(dialog, "accept")
    QTest.qWait(700)
    assert backend.catalogRoots == [{"identity": "test-volume", "root": "T:\\", "name": "Test drive", "enabled": False}]
    assert backend.catalog.count == 2  # Disabled entry edits do not restart the index.
    assert (tmp_path / "AllTheSmallThings/index.json").exists()
    assert QMetaObject.invokeMethod(window.findChild(QObject, "searchIndexAction"), "trigger")
    QTest.qWait(100)
    assert QMetaObject.invokeMethod(window.findChild(QObject, "removeDrive"), "click")
    assert QMetaObject.invokeMethod(window.findChild(QObject, "searchIndexDialog"), "reject")
    QTest.qWait(100)
    assert len(backend.catalogRoots) == 1
    window.close()
    backend.shutdown()
    engine.deleteLater()
    app.processEvents()
    assert not messages, messages


def test_catalog_reconfiguration_replaces_live_sources(monkeypatch, tmp_path):
    app = QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(Windows, "volumes", lambda self: iter(()))
    def wait_for(predicate, milliseconds):
        deadline = monotonic() + milliseconds / 1000
        while not predicate() and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)
        return predicate()

    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    (first_root / "first.txt").write_text("first")
    (second_root / "second.txt").write_text("second")
    backend = Backend()
    first = {"root": str(first_root) + "\\", "identity": "first", "name": "First", "enabled": True}
    second = {"root": str(second_root) + "\\", "identity": "second", "name": "Second", "enabled": True}
    backend.setCatalogRoots([first])
    assert wait_for(lambda: backend.resultCount == 1 and not backend.busy, 5000)
    assert backend.resultCount == 1
    assert backend.model.results.rows[0].entry.name == "first.txt"
    backend.setCatalogRoots([second])
    assert wait_for(lambda: not backend.busy and backend.resultCount == 1
                          and backend.model.results.rows[0].entry.name == "second.txt", 5000)
    assert backend.resultCount == 1
    assert backend.model.results.rows[0].entry.name == "second.txt"
    backend.setCatalogRoots([])
    assert wait_for(lambda: not backend.busy and backend.resultCount == 0, 5000)
    assert backend.resultCount == 0
    assert not backend.busy
    backend.shutdown()
    app.processEvents()


def test_catalog_tree_selection_filters_descendants(monkeypatch, tmp_path):
    from PySide6.QtCore import Q_ARG, QItemSelectionModel, QObject
    from test_tree import folder_catalog

    app = QGuiApplication.instance() or QGuiApplication([])
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(Windows, "volumes", lambda self: iter(()))
    backend = Backend()
    backend.settings.entries = [{"identity": "volume", "root": "C:\\", "name": "Drive", "enabled": True}]
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "smallthings/qml/Main.qml")))
    window = engine.rootObjects()[0]
    catalog = folder_catalog()
    backend.events.put(("catalog", catalog.sources))
    QTest.qWait(400)
    tree = window.findChild(QObject, "catalogTree")
    assert QMetaObject.invokeMethod(tree, "expand", Q_ARG(int, 0))
    QTest.qWait(100)
    drive = backend.tree.index(0, 0)
    docs = backend.tree.index(0, 0, drive)
    selection = tree.property("selectionModel")
    selection.setCurrentIndex(docs, QItemSelectionModel.ClearAndSelect)
    QTest.qWait(300)
    assert backend.selectedFolder == "10"
    assert {row.entry.name for row in backend.model.results.rows} == {"Nested", "a.txt", "b.txt"}
    assert QMetaObject.invokeMethod(tree, "expand", Q_ARG(int, 1))
    QTest.qWait(100)
    assert window.grabWindow().save("artifacts/ui-catalog-tree.png")
    source = catalog.sources[0]
    renamed = source.changed([(10, source.objects[10], (Entry(10, 5, "Renamed"),))], (1, 2))
    backend.events.put(("catalog", (renamed,)))
    QTest.qWait(300)
    assert backend.options.folder == "C:\\Renamed"
    assert backend.resultCount == 3
    removed = renamed.changed([(identity, None, ()) for identity in (10, 11, 12, 13)], (1, 3))
    backend.events.put(("catalog", (removed,)))
    QTest.qWait(300)
    assert backend.selectedFolder == ""
    assert backend.selectedRoot == "volume"
    assert backend.resultCount == 2
    assert QMetaObject.invokeMethod(window.findChild(QObject, "allLocations"), "click")
    QTest.qWait(300)
    assert backend.selectedRoot == ""
    assert backend.resultCount == 2
    window.close()
    backend.shutdown()
    engine.deleteLater()
    app.processEvents()
    assert not messages, messages

def test_normal_user_qml_index_report_and_live_refresh(monkeypatch, tmp_path):
    import ctypes
    import json

    from PySide6.QtCore import QObject

    assert not ctypes.windll.shell32.IsUserAnAdmin()
    app = QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    root = tmp_path / 'files'
    root.mkdir()
    (root / 'initial.txt').write_text('initial')
    settings = tmp_path / 'profile/AllTheSmallThings/index.json'
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps([
        {'identity': 'fixture', 'root': str(root) + '\\', 'name': 'Fixture', 'enabled': True},
        {'identity': 'denied', 'root': 'C:\\System Volume Information\\', 'name': 'Denied', 'enabled': True},
    ]))
    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({'backend': backend})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / 'smallthings/qml/Main.qml')))
    window = engine.rootObjects()[0]
    field = window.findChild(QObject, 'searchField')

    def wait_for(predicate):
        deadline = monotonic() + 10
        while not predicate() and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)
        assert predicate()

    wait_for(lambda: not backend.busy and backend.resultCount == 1)
    assert backend.indexIssueCount == 1
    assert QMetaObject.invokeMethod(window.findChild(QObject, 'indexIssuesButton'), 'click')
    wait_for(lambda: window.findChild(QObject, 'indexIssuesDialog') is not None)
    assert 'Access is denied' in backend.indexIssues[0]['reason']
    assert QMetaObject.invokeMethod(window.findChild(QObject, 'indexIssuesDialog'), 'reject')
    field.setProperty('text', 'initial')
    wait_for(lambda: not backend.searching and backend.resultCount == 1)
    backend.copyPath(0)
    assert app.clipboard().text() == str(root / 'initial.txt')
    (root / 'initial.txt').rename(root / 'renamed.txt')
    backend.refreshIndex()
    wait_for(lambda: backend.resultCount == 0)
    field.setProperty('text', 'renamed')
    wait_for(lambda: not backend.searching and backend.resultCount == 1)
    (root / 'renamed.txt').unlink()
    (root / 'created.txt').write_text('created')
    backend.refreshIndex()
    wait_for(lambda: backend.resultCount == 0)
    field.setProperty('text', 'created')
    wait_for(lambda: not backend.searching and backend.resultCount == 1)
    window.close()
    backend.shutdown()
    engine.deleteLater()
    app.processEvents()
    backend = Backend()
    backend.setQuery('created')
    wait_for(lambda: not backend.searching and backend.resultCount == 1)
    backend.shutdown()
