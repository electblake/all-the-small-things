import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml.Models

ColumnLayout {
    id: results
    required property QtObject backend
    required property FileActions fileActions
    required property font uiFont
    readonly property var selection: results.backend.resultModel.selectionModel
    readonly property int currentRow: results.backend.resultModel.currentRow
    spacing: 0
    FontMetrics {
        id: metrics
        font: results.uiFont
        onHeightChanged: table.forceLayout()
    }

    function selectRow(row, column) {
        results.selection.setCurrentIndex(results.backend.resultModel.index(row, column), ItemSelectionModel.ClearAndSelect | ItemSelectionModel.Rows)
        table.forceActiveFocus()
    }

    function focusResults() {
        table.forceActiveFocus()
        if (results.backend.resultModel.rowCount() > 0 && results.currentRow < 0)
            results.selection.setCurrentIndex(results.backend.resultModel.index(0, 0), ItemSelectionModel.ClearAndSelect | ItemSelectionModel.Rows)
    }

    HorizontalHeaderView {
        id: header
        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(32, Math.ceil(metrics.height) + 12)
        syncView: table
        clip: true
        resizableColumns: true
        delegate: ResultHeader {
            sortColumn: results.backend.sortColumn
            descending: results.backend.descending
            onClicked: results.backend.sortBy(column)
        }
    }
    Item {
        id: viewport
        Layout.fillWidth: true
        Layout.fillHeight: true

        TableView {
            id: table
            objectName: "resultsTable"
            anchors.fill: parent
            clip: true
            model: results.backend.resultModel
            selectionModel: results.selection
            selectionBehavior: TableView.SelectRows
            selectionMode: TableView.SingleSelection
            keyNavigationEnabled: true
            pointerNavigationEnabled: true
            reuseItems: true
            columnSpacing: 1
            rowSpacing: 0
            columnWidthProvider: function(column) {
                const count = 5
                const defaults = [240, 320, 100, 140, 190]
                const scale = metrics.height / 19
                let widths = []
                let total = count - 1
                for (let i = 0; i < count; ++i) {
                    const explicit = table.explicitColumnWidth(i)
                    widths[i] = explicit >= 0 ? explicit : Math.ceil(defaults[i] * scale)
                    total += widths[i]
                }
                // Stretch the path column while preserving horizontal scrolling at narrow widths.
                if (column === 1) return widths[column] + Math.max(0, table.width - total)
                return widths[column]
            }
            onWidthChanged: forceLayout()
            activeFocusOnTab: true
            Accessible.name: qsTr("Search results")
            Keys.onMenuPressed: if (results.currentRow >= 0) contextMenu.popup()

            rowHeightProvider: function(row) { return Math.max(30, Math.ceil(metrics.height) + 10) }
            delegate: ResultCell {
                tableFocused: table.activeFocus
                onActivated: (row, column) => results.selectRow(row, column)
                onOpened: (row, column) => {
                    results.selectRow(row, column)
                    results.fileActions.open.trigger()
                }
                onContextRequested: (row, column) => {
                    results.selectRow(row, column)
                    contextMenu.popup()
                }
            }
            ScrollBar.vertical: ScrollBar { policy: table.contentHeight > table.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
            ScrollBar.horizontal: ScrollBar { policy: table.contentWidth > table.width ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
            Menu {
                id: contextMenu
                MenuItem { action: results.fileActions.open }
                MenuItem { action: results.fileActions.reveal }
                MenuItem { action: results.fileActions.copy }
            }
        }
        Label {
            objectName: "emptyState"
            anchors.centerIn: viewport
            width: Math.max(0, viewport.width - 32)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            visible: results.backend.resultCount === 0 && !results.backend.busy && !results.backend.searching
            text: qsTr("No results")
        }
    }
}
