# Changelog

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
