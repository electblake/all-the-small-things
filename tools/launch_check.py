"""Launch the real application, record its first complete index and rendered UI."""
import json
import os
import sys
import tempfile
from pathlib import Path
from time import perf_counter

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
ARTIFACTS = PROJECT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
sys.stdout = (ARTIFACTS / "application.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
print("PID", os.getpid(), flush=True)
if "--headless" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from smallthings.backend import Backend

QQuickStyle.setStyle("Fusion")
app = QGuiApplication(sys.argv)
app.setApplicationName("All the Small Things")
backend = Backend()
engine = QQmlApplicationEngine()
engine.setInitialProperties({"backend": backend})
engine.load(QUrl.fromLocalFile(str(PROJECT / "smallthings/qml/Main.qml")))
window = engine.rootObjects()[0]
window.showNormal()
app.aboutToQuit.connect(backend.shutdown)
app.aboutToQuit.connect(lambda: print("Application closing", flush=True))
start = perf_counter()
query_started = None
stage = 0
fixture = Path(tempfile.mkdtemp(prefix="smallthings-ui-"))
original = fixture / f"__smallthings_{fixture.name}_original__.txt"
renamed = fixture / f"__smallthings_{fixture.name}_renamed__.txt"
report = {}


def check():
    global query_started, stage
    if backend.index_future.done():
        timer.stop()
        backend.index_future.result()
    if stage == 0 and not backend.busy:
        query_started = perf_counter()
        window.findChild(QObject, "searchField").setProperty("text", "AllTheSmallThings")
        stage = 1
    elif stage == 1 and backend.model.results.query == "AllTheSmallThings":
        assert backend.resultCount > 0
        backend.copyPath(0)
        assert app.clipboard().text()
        report.update(indexed=backend.catalog.count, matches=backend.resultCount,
                      query_observed_ms=(perf_counter() - query_started) * 1000, startup_seconds=perf_counter() - start,
                      sources=[source.root for source in backend.catalog.sources])
        print("Search passed", report, flush=True)
        original.write_text("live metadata", encoding="utf-8")
        window.findChild(QObject, "searchField").setProperty("text", original.name)
        stage = 2
    elif stage == 2 and backend.model.results.query == original.name and backend.resultCount == 1:
        assert backend.model.results.rows[0].metadata.size == 13
        original.rename(renamed)
        stage = 3
    elif stage == 3 and backend.resultCount == 0:
        window.findChild(QObject, "searchField").setProperty("text", renamed.name)
        stage = 4
    elif stage == 4 and backend.model.results.query == renamed.name and backend.resultCount == 1:
        renamed.unlink()
        stage = 5
    elif stage == 5 and backend.resultCount == 0:
        fixture.rmdir()
        window.findChild(QObject, "searchField").setProperty("text", "")
        stage = 6
    elif stage == 6 and backend.model.results.query == "" and backend.resultCount == backend.model.results.catalog.count:
        report["browsing_count"] = backend.resultCount
        assert backend.model.results.window(backend.resultCount - 1, 1)
        print("Live create, rename, delete and uncapped browsing passed", flush=True)
        window.findChild(QObject, "searchField").setProperty("text", "AllTheSmallThings")
        stage = 7
    elif stage == 7 and backend.model.results.query == "AllTheSmallThings":
        window.showNormal()
        if "--headless" not in sys.argv:
            window.raise_()
        assert window.grabWindow().save(str(ARTIFACTS / "application.png"))
        report["live_ui_checks"] = ["create", "rename", "delete", "copy path", "uncapped browsing"]
        (ARTIFACTS / "application.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("PASS", report, flush=True)
        timer.stop()
        stage = 8
        if "--headless" in sys.argv:
            app.quit()


timer = QTimer()
timer.timeout.connect(check)
timer.start(500)
exit_code = app.exec()
print("EXIT", exit_code, flush=True)
sys.exit(exit_code)
