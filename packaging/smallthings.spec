from pathlib import Path
import importlib.metadata
import sys
import tomllib
from PyInstaller.utils.win32.versioninfo import FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo

root = Path(SPECPATH).parent
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
version_tuple = tuple(map(int, version.split("."))) + (0,)
licenses = []
for name in ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6", "pcre2", "immutables"):
    distribution = importlib.metadata.distribution(name)
    for file in distribution.files:
        if any(part.lower().startswith(("license", "copying", "notice")) for part in file.parts):
            licenses.append((str(distribution.locate_file(file)), "licenses/" + name + "/" + "/".join(part for part in file.parent.parts if part != "..")))
licenses.append((str(Path(sys.base_prefix) / "LICENSE.txt"), "licenses/Python"))
a = Analysis([str(root / "packaging/entry.py")], pathex=[str(root)],
             datas=[(str(root / "smallthings/qml"), "smallthings/qml"),
                    (str(root / "packaging/licenses"), "licenses/Qt"),
                    (str(root / "packaging/THIRD-PARTY-NOTICES.txt"), "licenses")] + licenses,
             binaries=[], hiddenimports=[], hookspath=[str(root / "packaging/hooks")], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
metadata = VSVersionInfo(ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple,
    mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)), kids=[
    StringFileInfo([StringTable("040904B0", [StringStruct("CompanyName", "electblake"),
        StringStruct("FileDescription", "All the Small Things"), StringStruct("FileVersion", version),
        StringStruct("ProductName", "All the Small Things"), StringStruct("ProductVersion", version),
        StringStruct("OriginalFilename", "SmallThings.exe")])]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])])])
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SmallThings", console=False,
          debug=False, strip=False, upx=False, version=metadata)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SmallThings")
