import os
from dataclasses import replace
from pathlib import Path

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


def test_qml_search_sort_and_clipboard(monkeypatch, tmp_path):
    QQuickStyle.setStyle("Fusion")
    app = QGuiApplication.instance() or QGuiApplication([])
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    monkeypatch.setattr(Windows, "volumes", lambda self: iter(()))
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
    assert abs(table.property("contentWidth") - table.property("width")) <= 1
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
    window.close()
    backend.shutdown()
    engine.deleteLater()
    app.processEvents()
    assert not messages, messages
