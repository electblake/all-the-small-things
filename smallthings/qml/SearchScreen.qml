import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: screen
    required property QtObject backend
    required property FileActions fileActions
    required property font uiFont
    readonly property int currentRow: results.currentRow
    property bool showHelp: false
    spacing: 0

    function focusSearch() {
        toolbar.focusSearch()
    }

    SearchToolbar {
        id: toolbar
        Layout.fillWidth: true
        Layout.margins: 6
        backend: screen.backend
        onFocusResults: results.focusResults()
    }
    ResultsTable {
        id: results
        Layout.fillWidth: true
        Layout.fillHeight: true
        backend: screen.backend
        fileActions: screen.fileActions
        uiFont: screen.uiFont
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 8
        Layout.rightMargin: 8
        Layout.minimumHeight: 30
        spacing: 16
        Label {
            text: qsTr("%1 results").arg(screen.backend.resultCount.toLocaleString(Qt.locale(), 'f', 0))
        }
        Item { Layout.fillWidth: true }
        BusyIndicator {
            objectName: "activityIndicator"
            Layout.preferredWidth: 24
            Layout.preferredHeight: 24
            running: screen.backend.busy || screen.backend.searching
            visible: running
            Accessible.name: qsTr("Loading results")
        }
    }

    Loader {
        active: screen.showHelp
        sourceComponent: SyntaxDialog { onClosed: screen.showHelp = false }
        onLoaded: if (status === Loader.Ready) item.open()
    }
}
