# Changelog

## [Unreleased]

## [0.4.0] - 2026-10-23

### Added
- Added search history with Qt's built-in solid dropdown arrow and a list matching the search field width.
- Saved unique, successful queries with matching results, newest first; selecting an entry runs it again.
- Added Alt+Down to open history and Escape to dismiss it without clearing the query.

### Changed
- Stored catalog settings and search history with QSettings in the platformdirs user config directory.
- Included platformdirs and its license in the Windows installer.

### Fixed
- Preserved existing catalog choices through a one-time import from `index.json`, including disabled roots and empty catalogs.
- Excluded cancelled, failed, blank, zero-result, and outdated-catalog searches from history.
- Avoided rewriting unchanged history during background refreshes.
- Prevented searches from publishing results from an outdated catalog during indexing.
- Preserved typed text when history updates and restored popup keyboard focus.
- Corrected the README's encoding and outdated drive-support description.

## [0.3.0] - 2026-10-22

### Added
- Catalog-backed Qt TreeView with expandable drives and folders.
- Drive and descendant-folder search scopes, with All locations to clear the scope.
- Search Index dialog for adding, removing, naming, and enabling local and mapped network catalog roots.
- Persistent catalog settings and background index reconfiguration.

### Changed
- Catalog updates preserve unchanged tree branches; path-based folder renames reset the selected scope to its drive.
- Attached local, removable and network drives are available in the drive picker.
- Replaced raw-volume access with normal-user directory enumeration for local, removable and mapped network drives.
- Publish partial results during initial scans and preserve complete snapshots during background refresh.
- Report inaccessible paths and directory links without stopping other drives; add Rescan now.
- Removed automatic elevation from the source launcher.

### Fixed
- Isolate the build DLL search path so unrelated developer tools cannot supply incompatible runtime libraries.
- Replace the private runtime folder during upgrades so obsolete DLLs from 0.2.0 cannot break Qt loading.
- Stop polling a failed indexing task instead of repeatedly printing the same exception.
- Consume failed search tasks so later queries can run.
- Prevent tree model updates from changing the selected search scope to a neighboring folder.

## [0.2.0] - 2026-10-22

### Added
- First published Windows x64 release, with a self-contained per-user Inno Setup installer.
- PySide6 search interface with filename queries, metadata filters, sorting, and file actions.
- NTFS MFT indexing, persistent catalog, and USN journal updates.

### Changed
- Simplified UI to five columns, a result count, and one loading indicator.
- Shared file actions and corrected selection state after live deletions.
