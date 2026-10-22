import QtQuick
import QtQuick.Controls

MenuBar {
    id: menus
    required property QtObject backend
    required property FileActions fileActions
    signal focusSearch()
    signal showHelp()

    Menu {
        title: qsTr("&File")
        MenuItem { action: menus.fileActions.open }
        MenuItem { action: menus.fileActions.reveal }
        MenuSeparator {}
        Action { text: qsTr("E&xit"); shortcut: "Alt+F4"; onTriggered: Qt.quit() }
    }
    Menu {
        title: qsTr("&Edit")
        MenuItem { action: menus.fileActions.copy }
        Action { text: qsTr("&Search"); shortcut: "Ctrl+F"; onTriggered: menus.focusSearch() }
    }
    Menu {
        title: qsTr("&View")
        Action { text: qsTr("Folders &First"); checkable: true; checked: true; onToggled: menus.backend.setOption("folders_first", checked) }
    }
    Menu {
        title: qsTr("&Search")
        Action { text: qsTr("Match &Case"); shortcut: "Ctrl+I"; checkable: true; onToggled: menus.backend.setOption("case", checked) }
        Action { text: qsTr("Match Whole &Word"); shortcut: "Ctrl+B"; checkable: true; onToggled: menus.backend.setOption("words", checked) }
        Action { text: qsTr("Match &Path"); shortcut: "Ctrl+U"; checkable: true; onToggled: menus.backend.setOption("path", checked) }
        Action { text: qsTr("Enable &Regex"); shortcut: "Ctrl+R"; checkable: true; onToggled: menus.backend.setOption("regex", checked) }
    }
    Menu {
        title: qsTr("&Help")
        Action { text: qsTr("Search &Syntax"); shortcut: "F1"; onTriggered: menus.showHelp() }
    }
}
