import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    required property QtObject backend
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
    }
    SearchScreen {
        id: screen
        anchors.fill: parent
        backend: window.backend
        fileActions: fileActions
        uiFont: window.font
    }
}
