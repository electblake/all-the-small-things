from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Slot


@dataclass(eq=False)
class Node:
    identity: str = ""
    folder: int | None = None
    label: str = ""
    path: str = ""
    enabled: bool = True
    parent: object = None
    children: list | None = field(default=None)

    @property
    def key(self):
        return self.identity, self.folder


class CatalogTreeModel(QAbstractItemModel):
    def __init__(self):
        super().__init__()
        self.root = Node(children=[])
        self.sources = {}
        self.updating = False

    def roleNames(self):
        return {Qt.DisplayRole: b"display", Qt.UserRole: b"identity", Qt.UserRole + 1: b"folderId",
                Qt.UserRole + 2: b"path", Qt.UserRole + 3: b"available"}

    def children(self, node):
        if node.children is None:
            node.children = self.folder_nodes(node)
        return node.children

    def folder_nodes(self, node):
        if node.identity not in self.sources or not node.enabled:
            return []
        source = self.sources[node.identity]
        parent_id = source.root_id if node.folder is None else node.folder
        return [Node(node.identity, entry.object_id, entry.name, source.path(entry), True, node)
                for entry in source.folder_children.get(parent_id, ())]

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        node = parent.internalPointer() if parent.isValid() else self.root
        return self.createIndex(row, column, self.children(node)[row])

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer().parent
        return self.node_index(node)

    def node_index(self, node):
        if node is self.root:
            return QModelIndex()
        return self.createIndex(self.children(node.parent).index(node), 0, node)

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return 0
        return len(self.children(parent.internalPointer() if parent.isValid() else self.root))

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        return {Qt.DisplayRole: node.label, Qt.UserRole: node.identity,
                Qt.UserRole + 1: "" if node.folder is None else str(node.folder),
                Qt.UserRole + 2: node.path, Qt.UserRole + 3: node.enabled}.get(role)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable if index.internalPointer().enabled else Qt.NoItemFlags

    def publish(self, catalog, settings):
        self.updating = True
        self.sources = {source.identity: source for source in catalog.sources}
        roots = [Node(e["identity"], None, e["name"], e["root"], e["enabled"], self.root) for e in settings]
        self.reconcile(self.root, roots)
        self.updating = False

    def reconcile(self, parent, desired):
        children = self.children(parent)
        parent_index = self.node_index(parent)
        desired_keys = {node.key for node in desired}
        for row in range(len(children) - 1, -1, -1):
            if children[row].key not in desired_keys:
                self.beginRemoveRows(parent_index, row, row)
                children.pop(row)
                self.endRemoveRows()
        for row, replacement in enumerate(desired):
            existing = next((i for i, node in enumerate(children) if node.key == replacement.key), None)
            if existing is None:
                self.beginInsertRows(parent_index, row, row)
                children.insert(row, replacement)
                self.endInsertRows()
            elif existing != row:
                self.beginMoveRows(parent_index, existing, existing, parent_index, row)
                children.insert(row, children.pop(existing))
                self.endMoveRows()
            node = children[row]
            if (node.label, node.path, node.enabled) != (replacement.label, replacement.path, replacement.enabled):
                node.label, node.path, node.enabled = replacement.label, replacement.path, replacement.enabled
                index = self.node_index(node)
                self.dataChanged.emit(index, index)
            if node.children is not None:
                self.reconcile(node, self.folder_nodes(node))

    @Slot(QModelIndex, result="QVariantMap")
    def location(self, index):
        node = index.internalPointer()
        return {"identity": node.identity, "folder": "" if node.folder is None else str(node.folder)}
