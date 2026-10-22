import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml.Models

Pane {
    id: panel
    required property QtObject backend
    signal manageIndex()
    padding: 8
    ColumnLayout {
        anchors.fill: parent
        Label { text: qsTr("Files & Folders"); font.bold: true }
        ItemDelegate {
            objectName: "allLocations"
            Layout.fillWidth: true
            text: qsTr("All locations")
            highlighted: panel.backend.selectedRoot === ""
            onClicked: {
                tree.selectionModel.clearCurrentIndex()
                panel.backend.setRoot("")
            }
        }
        TreeView {
            id: tree
            objectName: "catalogTree"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: panel.backend.treeModel
            reuseItems: true
            selectionBehavior: TableView.SelectRows
            selectionMode: TableView.SingleSelection
            selectionModel: ItemSelectionModel {
                model: panel.backend.treeModel
                onCurrentChanged: function(current, previous) {
                    if (current.valid) {
                        const location = panel.backend.treeModel.location(current)
                        panel.backend.selectLocation(location.identity, location.folder)
                    }
                }
            }
            columnWidthProvider: function(column) { return tree.width }
            onWidthChanged: forceLayout()
            delegate: TreeViewDelegate {
                text: model.display
                enabled: model.available
                highlighted: panel.backend.selectedRoot === model.identity
                             && panel.backend.selectedFolder === model.folderId
                ToolTip.visible: hovered
                ToolTip.text: model.path
            }
            ScrollBar.vertical: ScrollBar {}
        }
        Button {
            Layout.fillWidth: true
            text: qsTr("Search Index…")
            onClicked: panel.manageIndex()
        }
    }
}
