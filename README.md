# All the Small Things

A Windows file and folder search application built with Python, PySide6, and QML. The interface follows Everything's basic layout: menus, a search box, a type filter, a sortable results table, and a status bar.

## Run

```powershell
uv sync
.\Start.ps1
```

Run from a normal Windows terminal:

```powershell
uv run smallthings
```

The application enumerates directories using the signed-in user's access. Neither launch nor installation requests elevation. Local, removable, and mapped network drives are supported regardless of filesystem; existing catalog selections are preserved. Search > Search Index manages roots and offers Rescan now.

Results become searchable during the initial scan. Complete snapshots are stored in `%LOCALAPPDATA%/AllTheSmallThings/filesystem.sqlite3`; the old raw-NTFS cache is not reused. Scans repeat 30 seconds after the preceding scan finishes, so changes on large drives may take longer to appear than with a USN journal. A previous complete snapshot remains searchable during refresh. No file contents are read.

Inaccessible folders and unavailable roots are listed in the indexing report, opened from the status bar. Indexing continues with other paths and drives. Directory junctions and symbolic links are listed but their targets are not traversed, preventing cycles and crossing catalog roots; these appear in the report too. Hidden and system entries are included when Windows permits enumeration. File identities are path-based; renaming a selected folder clears its folder scope back to its drive.

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

`tools/normal_user_check.py` exercises the real application entry point, every attached root, QML search input, root filtering and clipboard without elevation. It writes its report under `artifacts/`. The test suite also exercises actual filesystem changes, cache reload, and Windows access denials. The older raw-NTFS diagnostic tools remain developer utilities; they are not the application's indexing path.

Technical references: [Python directory enumeration](https://docs.python.org/3/library/os.html#os.scandir), [Everything documentation](https://www.voidtools.com/support/everything/), and [Qt for Python](https://doc.qt.io/qtforpython-6/).

## Windows installer

Download `AllTheSmallThings-0.4.0-windows-amd64-setup.exe` from the GitHub release. Setup installs the self-contained x64 application per user, adds a Start-menu shortcut, and provides an uninstaller. Python and uv are not required on the target machine. The catalog stays in Local AppData and is preserved when uninstalling.

Both the installer and application run without elevation. No drive is excluded by the scanner.

Build with PowerShell 7 and the installed Inno Setup compiler:

```powershell
pwsh -NoProfile -File packaging/build.ps1 -IsccPath 'C:/Users/shoji/AppData/Local/Programs/Inno Setup 6/ISCC.exe'
```

The script uses the locked build dependency group in `.build-venv`, stages a PyInstaller onedir bundle, compiles Setup, and writes `dist/installer/SHA256SUMS.txt`. Version metadata comes from `pyproject.toml`; the Inno AppId remains stable across upgrades. Release 0.4.0 is unsigned. See the release notes for validation results.

## Search index management

The resizable left **Files & Folders** panel uses Qt TreeView to display configured drives and expandable folders from the catalog. Selecting a drive filters to that catalog; selecting a folder filters to its contents and descendants. **All locations** clears the scope without changing the search text. The tree reads the index, not the filesystem, and updates as catalog changes arrive. Open **Search → Search Index** to add attached local, removable, or mapped network drives, rename catalog entries, pause indexing with the Index checkbox, or remove entries. Save applies changes; Cancel discards the draft. Removing a root removes its search results, not its files or cached metadata.

Catalog settings and search history use QSettings in `settings.ini` inside the user config directory selected by platformdirs (`%LOCALAPPDATA%/AllTheSmallThings` on Windows). Existing `index.json` catalog choices are imported once when the QSettings catalog is first created; later changes use `settings.ini`. The search field's built-in Qt dropdown lists successful, nonempty queries with matching results, newest first and without duplicates. Select an entry to search again; Alt+Down opens the list and Escape dismisses it. Cancelled, failed, blank, zero-result, and outdated-catalog searches are not recorded. The initial catalog retains the automatically discovered fixed NTFS drives. Saved empty catalogs remain empty. The panel uses a Qt Quick SplitView; it is resizable, not a floating QDockWidget.
