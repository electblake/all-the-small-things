import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    required property QtObject backend
    property bool showIndex: false
    width: 1200
    height: 760
    minimumWidth: 640
    minimumHeight: 360
    visible: true
    color: palette.base
    title: qsTr("All the Small Things")
    font.family: "Segoe UI"
    font.pointSize: 12
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true
    FileActions {
        id: fileActions
        backend: window.backend
        currentRow: screen.currentRow
    }
    menuBar: SearchMenus {
        backend: window.backend
        fileActions: fileActions
        onFocusSearch: screen.focusSearch()
        onShowHelp: screen.showHelp = true
        onShowIndex: window.showIndex = true
    }
    SplitView {
        anchors.fill: parent
        orientation: Qt.Horizontal
        CatalogPanel {
            SplitView.preferredWidth: 220
            SplitView.minimumWidth: 150
            backend: window.backend
            onManageIndex: window.showIndex = true
        }
        SearchScreen {
            id: screen
            SplitView.fillWidth: true
            SplitView.minimumWidth: 420
            backend: window.backend
            fileActions: fileActions
            uiFont: window.font
        }
    }
    Loader {
        active: window.showIndex
        sourceComponent: SearchIndexDialog {
            backend: window.backend
            onClosed: window.showIndex = false
        }
        onLoaded: if (status === Loader.Ready) item.open()
    }
}
