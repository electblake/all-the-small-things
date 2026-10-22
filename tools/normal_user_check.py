"""Exercise the actual entry point, backend, Windows roots, QML input and results without elevation."""
import ctypes
import json
import os
import sys
import tempfile
from pathlib import Path
from time import monotonic
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project))
from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QGuiApplication
from smallthings import app as application
from smallthings.ntfs import Windows

assert not ctypes.windll.shell32.IsUserAnAdmin()
expected = list(Windows().volumes())
profile = tempfile.mkdtemp(prefix='smallthings-standard-user-')
os.environ['LOCALAPPDATA'] = profile
report = {'elevated': False, 'roots': [root for root, _ in expected], 'searches': []}
original_exec = QGuiApplication.exec
started = monotonic()
state = {'position': 0, 'query': None}

def checked_exec(app):
    window = next(w for w in app.allWindows() if w.property('backend') is not None)
    backend = window.property('backend')
    field = window.findChild(QObject, 'searchField')
    def check():
        assert monotonic() - started < 180, 'Timed out waiting for real drive search'
        if backend.index_future.done():
            backend.index_future.result()
        if state['position'] == len(expected):
            report['issues'] = backend.indexIssues
            report['indexed_so_far'] = backend.catalog.count
            report['seconds'] = monotonic() - started
            assert backend.indexIssueCount > 0
            assert {s.identity for s in backend.catalog.sources} == {identity for _, identity in expected}
            assert window.grabWindow().save(str(project / 'artifacts/normal-user-startup.png'))
            (project / 'artifacts/normal-user-startup.json').write_text(json.dumps(report, indent=2))
            timer.stop()
            app.quit()
            return
        root, identity = expected[state['position']]
        sources = [s for s in backend.catalog.sources if s.identity == identity and s.count]
        if not sources:
            return
        if state['query'] is None:
            entry = next(sources[0].entries)
            state['query'] = '"' + entry.name + '"'
            state['name'] = entry.name
            backend.setRoot(identity)
            field.setProperty('text', state['query'])
        elif not backend.searching and backend.model.results.query == state['query']:
            assert backend.resultCount > 0
            assert any(row.entry.name == state['name'] for row in backend.model.results.rows)
            assert all(row.source.identity == identity for row in backend.model.results.rows)
            backend.copyPath(0)
            assert app.clipboard().text().startswith(root)
            report['searches'].append({'root': root, 'query': state['query'], 'matches': backend.resultCount})
            print(report['searches'][-1], flush=True)
            state['position'] += 1
            state['query'] = None
    timer = QTimer()
    timer.timeout.connect(check)
    timer.start(100)
    def fail(kind, value, traceback):
        sys.__excepthook__(kind, value, traceback)
        timer.stop()
        app.exit(1)
    sys.excepthook = fail
    return original_exec()

with patch.object(QGuiApplication, 'exec', checked_exec):
    result = application.main()
assert result == 0
print('PASS', json.dumps({key: value for key, value in report.items() if key != 'issues'}), flush=True)
