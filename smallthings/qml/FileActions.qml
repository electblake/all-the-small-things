import QtQuick
import QtQuick.Controls

QtObject {
    id: actions
    required property QtObject backend
    required property int currentRow
    readonly property Action open: Action {
        objectName: "openAction"
        text: qsTr("&Open")
        shortcut: "Return"
        enabled: actions.currentRow >= 0
        onTriggered: actions.backend.openRow(actions.currentRow)
    }
    readonly property Action reveal: Action {
        objectName: "revealAction"
        text: qsTr("Open &Path")
        shortcut: "Ctrl+Return"
        enabled: actions.currentRow >= 0
        onTriggered: actions.backend.revealRow(actions.currentRow)
    }
    readonly property Action copy: Action {
        objectName: "copyAction"
        text: qsTr("&Copy Full Path")
        shortcut: "Ctrl+Shift+C"
        enabled: actions.currentRow >= 0
        onTriggered: actions.backend.copyPath(actions.currentRow)
    }
}
