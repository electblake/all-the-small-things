import ntpath
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from queue import SimpleQueue
from threading import Event

from PySide6.QtCore import (
    Property,
    QAbstractTableModel,
    QDateTime,
    QItemSelectionModel,
    QLocale,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication

from .catalog import Catalog
from .filesystem import scan
from .index_settings import IndexSettings
from .ntfs import Windows
from .search import EPOCH, Options, Results, search
from .storage import Store
from .tree_model import CatalogTreeModel


class ResultModel(QAbstractTableModel):
    currentRowChanged = Signal()
    columns = (("Name", "name"), ("Path", "path"), ("Size", "size"),
               ("Type", "extension"), ("Date Modified", "modified"))

    def __init__(self):
        super().__init__()
        self.results = Results(Catalog(()), [])
        self.locale = QLocale()
        self.selection = QItemSelectionModel(self, self)
        self.selection.currentChanged.connect(self.currentRowChanged)
        self.modelReset.connect(self.currentRowChanged)

    selectionModel = Property(QObject, lambda self: self.selection, constant=True)
    currentRow = Property(int, lambda self: self.selection.currentIndex().row(), notify=currentRowChanged)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.results.total

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def roleNames(self):
        return {Qt.ItemDataRole.DisplayRole: b"display", Qt.ItemDataRole.UserRole: b"folder"}

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.tr(self.columns[section][0])

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.results.rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return row.metadata.folder
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        column = index.column()
        if column == 0:
            return row.entry.name
        if column == 1:
            return ntpath.dirname(row.path)
        if column == 2:
            return "" if row.metadata.size is None else self.locale.formattedDataSize(row.metadata.size)
        if column == 3:
            return self.tr("File folder") if row.metadata.folder else (
                self.tr("%1 file").replace("%1", row.entry.extension.upper()) if row.entry.extension else self.tr("File"))
        timestamp = row.metadata.modified
        if timestamp is None:
            return ""
        date = QDateTime.fromMSecsSinceEpoch((timestamp - EPOCH) // 10_000)
        return self.locale.toString(date, QLocale.FormatType.ShortFormat)

    def publish(self, results):
        same_query = self.results.query == results.query
        current = self.selection.currentIndex()
        selected = self.results.rows[current.row()] if current.isValid() else None
        self.beginResetModel()
        self.results = results
        restored = -1
        if same_query and selected is not None and any(
                source.identity == selected.source.identity for source in results.catalog.sources):
            restored = results.index_of(selected)
        if restored < 0 and results.total:
            restored = 0
        self.endResetModel()
        if restored >= 0:
            self.selection.setCurrentIndex(self.index(restored, 0),
                                           QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)


class Backend(QObject):
    changed = Signal()
    indexSettingsChanged = Signal()
    availableDrivesChanged = Signal()

    def __init__(self, roots=()):
        super().__init__()
        self.model = ResultModel()
        self.tree = CatalogTreeModel()
        self._selected_folder = ""
        self.options = Options()
        self.catalog = Catalog(())
        self.query = ""
        self._busy = True
        self.events = SimpleQueue()
        self.stopped = Event()
        self.cancelled = Event()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="smallthings")
        available = list(Windows().volumes())
        if roots:
            available = [(root, identity) for root, identity in available if root[:2].upper() in roots]
        self.settings = IndexSettings(Path(os.environ["LOCALAPPDATA"]) / "AllTheSmallThings" / "index.json", available)
        self.tree.publish(self.catalog, self.settings.entries)
        self._available_drives = []
        self._index_issues = {}
        self.rescan = Event()
        self._restart_index = False
        self.index_future = self.executor.submit(self.index_volumes, self.settings.entries)
        self.query_future = None
        self.pending_query = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(50)

    catalogRoots = Property("QVariantList", lambda self: self.settings.entries, notify=indexSettingsChanged)
    availableDrives = Property("QVariantList", lambda self: self._available_drives, notify=availableDrivesChanged)

    @Slot()
    def refreshDrives(self):
        self._available_drives = list(Windows().drives())
        self.availableDrivesChanged.emit()

    @Slot("QVariantList")
    def setCatalogRoots(self, entries):
        before = [(entry["root"], entry["identity"]) for entry in self.settings.entries if entry["enabled"]]
        after = [(entry["root"], entry["identity"]) for entry in entries if entry["enabled"]]
        self.settings.save(entries)
        if self.options.root and not any(entry["identity"] == self.options.root and entry["enabled"] for entry in entries):
            self.setRoot("")
        self.tree.publish(self.catalog, self.settings.entries)
        self.indexSettingsChanged.emit()
        if before == after:
            return
        self._restart_index = True
        self._busy = True
        self.cancelled.set()
        self.stopped.set()
        self.rescan.set()
        self.changed.emit()

    treeModel = Property(QObject, lambda self: self.tree, constant=True)
    selectedFolder = Property(str, lambda self: self._selected_folder, notify=changed)
    selectedRoot = Property(str, lambda self: self.options.root, notify=changed)
    resultModel = Property(QObject, lambda self: self.model, constant=True)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    searching = Property(bool, lambda self: self.query_future is not None or self.pending_query, notify=changed)
    resultCount = Property(int, lambda self: self.model.results.total, notify=changed)
    sortColumn = Property(int, lambda self: tuple(key for _, key in ResultModel.columns).index(self.options.sort), notify=changed)
    descending = Property(bool, lambda self: self.options.descending, notify=changed)

    indexIssues = Property("QVariantList", lambda self: [
        {"path": path, "reason": reason} for path, reason in self._index_issues.items()], notify=changed)
    indexIssueCount = Property(int, lambda self: len(self._index_issues), notify=changed)

    @Slot()
    def refreshIndex(self):
        self.rescan.set()

    def index_volumes(self, roots):
        cache = Path(os.environ["LOCALAPPDATA"]) / "AllTheSmallThings"
        cache.mkdir(exist_ok=True)
        store = Store(cache / "filesystem.sqlite3")
        entries = [entry for entry in roots if entry["enabled"]]
        sources = {}
        for entry in entries:
            if self.stopped.is_set():
                break
            if store.contains(entry["identity"]):
                sources[entry["identity"]] = store.load(entry["identity"], entry["root"])
        self.events.put(("catalog", tuple(sources.values())))
        while not self.stopped.is_set():
            self.rescan.clear()
            self.events.put(("scan", None))
            report = lambda path, reason: self.events.put(("issue", (path, reason)))
            scans = [(entry["identity"], scan(entry["root"], entry["identity"], self.stopped, report))
                     for entry in entries]
            while scans and not self.stopped.is_set():
                remaining = []
                for identity, iterator in scans:
                    if self.stopped.is_set():
                        break
                    batch = next(iterator, None)
                    if batch is None:
                        continue
                    source, complete = batch
                    # Keep the previous complete snapshot searchable during refresh.
                    if identity not in sources or complete or sources[identity].position == (0, -1):
                        source.position = (0, 0 if complete else -1)
                        sources[identity] = source
                        self.events.put(("catalog", tuple(sources.values())))
                    if complete:
                        store.replace(source)
                    else:
                        remaining.append((identity, iterator))
                scans = remaining
            self.events.put(("ready", None))
            if self.stopped.is_set():
                break
            self.rescan.wait(30)
        store.close()

    @Slot()
    def poll(self):
        if self.index_future.done():
            self.timer.stop()
            self.index_future.result()
            if self._restart_index:
                self._restart_index = False
                while not self.events.empty():
                    self.events.get()
                self.catalog = Catalog((), self.catalog.generation + 1)
                self.model.publish(Results(self.catalog, [], self.query, self.options))
                self.pending_query = True
                self.stopped = Event()
                self.index_future = self.executor.submit(self.index_volumes, self.settings.entries)
                self.timer.start()
                self.changed.emit()
        if self._restart_index:
            return
        while not self.events.empty():
            kind, data = self.events.get()
            if kind == "catalog":
                self.catalog = Catalog(data, self.catalog.generation + 1)
                self.tree.publish(self.catalog, self.settings.entries)
                if self._selected_folder and any(s.identity == self.options.root for s in self.catalog.sources):
                    source = next(s for s in self.catalog.sources if s.identity == self.options.root)
                    identity = int(self._selected_folder)
                    if identity in source.links:
                        self.options = replace(self.options, folder=source.path(source.links[identity][0]))
                    else:
                        self.setRoot(self.options.root)
                self.pending_query = True
            elif kind == "scan":
                self._index_issues.clear()
                self._busy = True
            elif kind == "issue":
                self._index_issues[data[0]] = data[1]
            elif kind == "ready":
                self._busy = False
            self.changed.emit()
        if self.query_future is not None and self.query_future.done():
            completed = self.query_future
            self.query_future = None
            result = completed.result()
            if result is not None and not self.cancelled.is_set():
                self.model.publish(result)
                self.changed.emit()
        if self.pending_query and self.query_future is None and (self.query or self.catalog.sources or not self._busy):
            self.pending_query = False
            self.cancelled = Event()
            self.query_future = self.executor.submit(search, self.catalog, self.query, self.options,
                                                     self.cancelled, self.model.results)
            self.changed.emit()

    def request_search(self):
        self.cancelled.set()
        self.pending_query = True
        self.changed.emit()

    @Slot(str)
    def setRoot(self, identity):
        self._selected_folder = ""
        self.options = replace(self.options, root=identity, folder="")
        self.request_search()

    @Slot(str, str)
    def selectLocation(self, identity, folder):
        if self.tree.updating:
            return
        if not folder:
            self.setRoot(identity)
            return
        source = next(s for s in self.catalog.sources if s.identity == identity)
        self._selected_folder = folder
        self.options = replace(self.options, root=identity, folder=source.path(source.links[int(folder)][0]))
        self.request_search()

    @Slot(str)
    def setQuery(self, value):
        self.query = value
        self.request_search()

    @Slot(str, bool)
    def setOption(self, name, value):
        self.options = replace(self.options, **{name: value})
        self.request_search()

    @Slot(str)
    def setKind(self, value):
        self.options = replace(self.options, kind=value)
        self.request_search()

    @Slot(int)
    def sortBy(self, column):
        key = ResultModel.columns[column][1]
        self.options = replace(self.options, sort=key, descending=(not self.options.descending if key == self.options.sort else False))
        self.request_search()
        self.changed.emit()

    @Slot(int)
    def openRow(self, index):
        os.startfile(self.model.results.rows[index].path)

    @Slot(int)
    def revealRow(self, index):
        subprocess.Popen(["explorer.exe", "/select,", self.model.results.rows[index].path])

    @Slot(int)
    def copyPath(self, index):
        QGuiApplication.clipboard().setText(self.model.results.rows[index].path)

    @Slot()
    def shutdown(self):
        self.timer.stop()
        self.stopped.set()
        self.rescan.set()
        self.cancelled.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.index_future.result()
