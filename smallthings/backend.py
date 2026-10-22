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
from .ntfs import Volume, Windows
from .search import EPOCH, Options, Results, search
from .storage import Store


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
        if same_query and selected is not None:
            restored = results.index_of(selected)
        if restored < 0 and results.total:
            restored = 0
        self.endResetModel()
        if restored >= 0:
            self.selection.setCurrentIndex(self.index(restored, 0),
                                           QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)


class Backend(QObject):
    changed = Signal()

    def __init__(self, roots=()):
        super().__init__()
        self.model = ResultModel()
        self.options = Options()
        self.catalog = Catalog(())
        self.query = ""
        self._busy = True
        self.events = SimpleQueue()
        self.stopped = Event()
        self.cancelled = Event()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="smallthings")
        self.index_future = self.executor.submit(self.index_volumes, roots)
        self.query_future = None
        self.pending_query = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(50)

    resultModel = Property(QObject, lambda self: self.model, constant=True)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    searching = Property(bool, lambda self: self.query_future is not None or self.pending_query, notify=changed)
    resultCount = Property(int, lambda self: self.model.results.total, notify=changed)
    sortColumn = Property(int, lambda self: tuple(key for _, key in ResultModel.columns).index(self.options.sort), notify=changed)
    descending = Property(bool, lambda self: self.options.descending, notify=changed)

    def index_volumes(self, roots):
        cache = Path(os.environ["LOCALAPPDATA"]) / "AllTheSmallThings"
        cache.mkdir(exist_ok=True)
        store = Store(cache / "catalog.sqlite3")
        sources, volumes = [], []
        for root, identity in Windows().volumes():
            if roots and root[:2].upper() not in roots:
                continue
            if self.stopped.is_set():
                return
            volume = Volume(root, identity)
            volumes.append(volume)
            if store.contains(identity):
                source = volume.changes(store.load(identity, root), store)
            else:
                source = volume.enumerate(None, self.stopped)
                if source is not None:
                    store.replace(source)
            if source is None:
                break
            sources.append(source)
            self.events.put(("catalog", tuple(sources)))
        self.events.put(("ready", None))
        while not self.stopped.wait(0.5):
            updated = []
            for volume, source in zip(volumes, sources):
                updated.append(volume.changes(source, store))
            if any(before is not after for before, after in zip(sources, updated)):
                sources = updated
                self.events.put(("catalog", tuple(sources)))
        for volume in volumes:
            volume.close()
        store.close()

    @Slot()
    def poll(self):
        if self.index_future.done():
            self.timer.stop()
            self.index_future.result()
        while not self.events.empty():
            kind, data = self.events.get()
            if kind == "catalog":
                self.catalog = Catalog(data, self.catalog.generation + 1)
                self.pending_query = True
            elif kind == "ready":
                self._busy = False
            self.changed.emit()
        if self.query_future is not None and self.query_future.done():
            result = self.query_future.result()
            self.query_future = None
            if result is not None and not self.cancelled.is_set():
                self.model.publish(result)
                self.changed.emit()
        if self.pending_query and self.query_future is None and (self.query or not self._busy):
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
        self.cancelled.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.index_future.result()
