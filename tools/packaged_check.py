"""Black-box UI Automation check for the source command or installed executable."""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from time import monotonic, sleep

import psutil
from pywinauto import Desktop

assert not ctypes.windll.shell32.IsUserAnAdmin()
project = Path(__file__).resolve().parents[1]
profile = Path(tempfile.mkdtemp(prefix='smallthings-packaged-check-'))
root = profile / 'files'
root.mkdir()
(root / 'release-smoke-needle.txt').write_text('release smoke')
settings = profile / 'AllTheSmallThings/index.json'
settings.parent.mkdir()
settings.write_text(json.dumps([
    {'identity': 'fixture', 'root': str(root) + '\\', 'name': 'Fixture', 'enabled': True},
    {'identity': 'denied', 'root': 'C:\\System Volume Information\\', 'name': 'Denied', 'enabled': True},
]))
env = dict(os.environ, LOCALAPPDATA=str(profile))
env.pop('QT_QPA_PLATFORM', None)
env.pop('PYTHONPATH', None)
env.pop('VIRTUAL_ENV', None)
command = ['uv', 'run', 'smallthings'] if sys.argv[1] == 'source' else [str(Path(sys.argv[1]).resolve())]
if sys.argv[1] != 'source':
    env['PATH'] = os.environ['SystemRoot'] + r'\System32;' + os.environ['SystemRoot']
process = subprocess.Popen(command, cwd=project if sys.argv[1] == 'source' else profile, env=env)
deadline = monotonic() + 120
window = None
while window is None and monotonic() < deadline:
    processes = {process.pid} | {p.pid for p in psutil.Process(process.pid).children(recursive=True)}
    windows = [w for w in Desktop(backend='uia').windows(title='All the Small Things') if w.process_id() in processes]
    if windows:
        window = windows[0]
    sleep(0.1)
assert window is not None, 'Application window did not appear'
window = Desktop(backend='uia').window(handle=window.handle)
print('Window ready', flush=True)
edit = window.child_window(control_type='Edit', found_index=0).wrapper_object()
edit.set_edit_text('release-smoke-needle')
while monotonic() < deadline:
    texts = [c.window_text() for c in window.descendants()]
    if 'release-smoke-needle.txt' in texts and '1 results' in texts:
        break
    sleep(0.2)
assert 'release-smoke-needle.txt' in texts, texts
assert '1 results' in texts, texts
assert any('indexing notices' in text for text in texts), texts
edit.set_edit_text('definitely-no-matching-release-file')
while monotonic() < deadline:
    texts = [c.window_text() for c in window.descendants()]
    if '0 results' in texts:
        break
    sleep(0.2)
assert '0 results' in texts
window.capture_as_image().save(project / 'artifacts' / ('source-launch.png' if sys.argv[1] == 'source' else 'packaged-launch.png'))
window.close()
assert process.wait(timeout=20) == 0
print('PASS', command, 'non-elevated startup, search match/no-match, access report, clean exit', flush=True)
