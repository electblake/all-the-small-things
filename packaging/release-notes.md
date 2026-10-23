## Search history and persistent settings

- Added Qt's built-in solid dropdown arrow at the end of the search field. The history popup matches the field width; selecting a query searches again. Alt+Down opens history and Escape dismisses it.
- Saved unique, nonempty queries with matching results, newest first. Cancelled, failed, blank, zero-result, and outdated-catalog searches are excluded.
- Stored catalog settings and history together through QSettings and platformdirs in `%LOCALAPPDATA%/AllTheSmallThings/settings.ini` on Windows.
- Imported existing `index.json` catalog settings once, preserving custom names, disabled roots, and empty catalogs. The original file remains intact; subsequent settings changes use QSettings.
- Fixed popup keyboard focus, avoided unchanged history writes during background refreshes, and prevented stale catalog search results from being displayed.
- Bundled platformdirs and its MIT license and declared the Windows smoke-test dependencies.

The Windows AMD64 installer includes Python and Qt, installs per user without elevation, and retains the existing AppId. The installer is unsigned. `SHA256SUMS.txt` contains its SHA-256 digest.

Validation: 55 tests and repository-wide lint passed. Windows UI Automation checked source and packaged applications for search matches, zero results, catalog migration, persisted history, access reporting, and clean exit. Per-user silent installation, upgrade from 0.3.0, and uninstall with settings preservation were checked on the Windows host. These checks are not a separate clean-VM certification.
