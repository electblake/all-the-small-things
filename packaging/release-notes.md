First published release of All the Small Things.

- Windows x64 per-user Setup installer, including Python, Qt/QML, and native dependencies.
- Filename and metadata search with persistent NTFS catalog and USN journal updates.
- Five-column results table, sorting, shared file actions, keyboard navigation, and simplified status display.
- Source entry point: `uv run smallthings`.

Download the setup executable below. SHA256SUMS.txt contains its SHA-256 digest. The installer is unsigned and does not require administrator privileges to install. Raw NTFS indexing still requires running the application with administrator privileges; no drives are excluded.

Validation: 38 source tests passed before packaging. Frozen-app launch and installer install/upgrade/uninstall tests were not run, as requested.
