# All the Small Things

A Windows file and folder search application built with Python, PySide6, and QML. The interface follows Everything's basic layout: menus, a search box, a type filter, a sortable results table, and a status bar.

## Run

```powershell
uv sync
.\Start.ps1
```

The launcher requests Windows elevation for read-only raw-volume access. The application discovers local fixed NTFS volumes, reads the MFT, and keeps its catalog current using the USN journal. Journals must already exist. Filesystem access and query failures propagate; there is no directory-walking substitute.

When already running in an elevated terminal:

```powershell
uv run smallthings
```

The first scan reads filesystem metadata. Subsequent launches load the SQLite metadata catalog from `%LOCALAPPDATA%\AllTheSmallThings\catalog.sqlite3` and replay journal changes. No file contents are indexed. Catalogs retain separate hardlinks, full record sequence identities, and parent relationships for directory moves.

## Search

| Query | Meaning |
|---|---|
| `report` | Filename substring |
| `report 2026` | Both terms |
| `red blue \| green` | `red AND (blue OR green)` |
| `<red blue> \| green` | Grouped expression |
| `!draft` | Exclude a term |
| `"annual report"` | Literal phrase |
| `*.pdf` | Whole-name wildcard |
| `C:\Projects\**.py` | Wildcard across path separators |
| `file:` / `folder:` | Entry kind |
| `ext:jpg;png` | Extensions |
| `size:1kb` | 1024–2047 bytes |
| `size:=1kb` | Exactly 1024 bytes |
| `size:>10mb` | Size comparison |
| `dm:today` / `dc:2026-10` / `da:thisweek` | Metadata dates |
| `attrib:rh` | Read-only and hidden |
| `path:src` | Full-path matching |
| `case:Report` | Case-sensitive term |
| `wholewords:report` | Whole-word term |
| `regex:^report.*` | PCRE2 expression |

The Search menu sets case, whole-word, path, and PCRE2 regex modes. `no-case:`, `no-wholewords:`, and `no-path:` override corresponding settings for a term. Global regex mode interprets the complete input as an expression. Content search, macros, and saved filters are outside this implementation's scope.

Click a column heading to sort; click again to reverse it. The table shows name, path, size, type, and date modified. Created and accessed dates remain searchable through `dc:` and `da:`. Results are virtualized with no 5,000-row cap, and each published result set holds a coherent catalog snapshot. Columns fill the available width; narrow windows scroll horizontally. Headers remain synchronized when scrolling, columns can be resized, and hovering truncated text reveals its full value. Empty-state messages remain centered in the viewport. The interface follows the system palette and accommodates larger fonts, including scrollable search help.

## Keyboard

| Key | Action |
|---|---|
| Ctrl+F | Focus and select search text |
| Down from search | Focus results |
| Enter / double-click | Open selection |
| Ctrl+Enter | Reveal in Explorer |
| Ctrl+Shift+C | Copy full path |
| Escape in search | Clear query |
| Ctrl+I / Ctrl+B / Ctrl+U / Ctrl+R | Case / word / path / regex |
| F1 | Search syntax |

## Verification

```powershell
uv run pytest -q
uv run ruff check smallthings
```

`tools/live_check.py` is an elevated integration check that reads the real MFT and verifies hardlinks, renames, metadata updates, deletions, and searching against temporary test files. `tools/launch_check.py` opens the real application and records its completed startup, search, clipboard check, and screenshot under `artifacts/`.

Technical references: the supplied catalog, index, NTFS, and search specifications; [Everything documentation](https://www.voidtools.com/support/everything/); [Microsoft change journals](https://learn.microsoft.com/en-us/windows/win32/fileio/change-journal-operations); [Qt for Python](https://doc.qt.io/qtforpython-6/).

## Windows installer

Download `AllTheSmallThings-0.2.0-windows-amd64-setup.exe` from the GitHub release. Setup installs the self-contained x64 application per user, adds a Start-menu shortcut, and provides an uninstaller. Python and uv are not required on the target machine. The catalog stays in Local AppData and is preserved when uninstalling.

The installer does not request elevation. The application's existing raw NTFS indexing path requires an elevated application process. Source launch remains `uv run smallthings` from an elevated terminal; the installed shortcut can be run as administrator. No volumes are excluded.

Build with PowerShell 7 and the installed Inno Setup compiler:

```powershell
pwsh -NoProfile -File packaging/build.ps1 -IsccPath 'C:/Users/shoji/AppData/Local/Programs/Inno Setup 6/ISCC.exe'
```

The script uses the locked build dependency group in `.build-venv`, stages a PyInstaller onedir bundle, compiles Setup, and writes `dist/installer/SHA256SUMS.txt`. Version metadata comes from `pyproject.toml`; the Inno AppId remains stable across upgrades. Release 0.2.0 is unsigned. Installer runtime/upgrade/uninstall testing was not performed for this release.
