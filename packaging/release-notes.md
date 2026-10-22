## Normal-user indexing, catalog tree, and index management

- The app and installer run without administrator access. Directory enumeration replaces raw NTFS volume access.
- Local, removable, and mapped network drives are supported. Inaccessible folders and unavailable roots are reported while other paths continue indexing.
- Search results appear during the initial scan. Complete snapshots are cached; background rescans retain the previous complete snapshot until replacement. Rescans start 30 seconds after the previous scan finishes, or through Search > Search Index > Rescan now.
- Files & Folders is an expandable catalog-backed tree. Selecting a drive or folder filters results to that location and its descendants.
- Search > Search Index adds/removes drives and edits their names and enabled state.
- Fixed repeated indexing exceptions, failed queries blocking subsequent searches, and tree updates silently selecting a neighboring folder.
- Isolated the packaging DLL search path and replaced the private runtime folder during upgrades to remove incompatible DLLs from 0.2.0.

Directory links are listed without traversing their targets, preventing cycles. Other reparse directories, including cloud-provider directories, are enumerated normally when accessible. Hidden/system entries are included when Windows permits access. Path-based folder renames reset the selected folder scope to its drive. Initial scans and refreshes can take longer than raw-MFT indexing. Existing raw-NTFS caches are left intact; the new cache is filesystem.sqlite3 in Local AppData.

The Windows AMD64 installer includes Python and Qt, installs per user, and retains the existing AppId. The installer is unsigned. SHA256SUMS.txt contains its SHA-256 digest.

Validation: 51 tests and lint passed. The real application entry point searched all 10 attached drives (including mapped network drives) under a non-elevated process while initial indexing continued. Windows UI Automation exercised uv run smallthings and the frozen/installed app: search matches, no matches, access-denied reporting, and clean exit. Actual filesystem create/rename/delete, rescan, cache reload, and protected-directory access were tested. Per-user silent installation, upgrade from 0.2.0 (including removal of its stale ICU DLL), and uninstall/data preservation passed. These are Windows host checks, not a separate clean-VM certification.
