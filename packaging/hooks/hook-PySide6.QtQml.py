import json
import subprocess
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
root = Path(__file__).resolve().parents[2]
qml_root = Path(pyside6_library_info.location["QmlImportsPath"])
scanner = qml_root.parent / "qmlimportscanner.exe"
modules = json.loads(subprocess.check_output([
    str(scanner), "-rootPath", str(root / "smallthings/qml"), "-importPath", str(qml_root)
], text=True))
for module in modules:
    # Built-in QML language modules have no on-disk payload.
    if "path" not in module:
        continue
    source = Path(module["path"])
    destination = "PySide6/qml/" + source.relative_to(qml_root).as_posix()
    for file in source.iterdir():
        if file.is_file():
            target = binaries if file.suffix.lower() == ".dll" else datas
            target.append((str(file), destination))
