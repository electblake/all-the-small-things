import QtQuick
import QtQuick.Controls.Fusion
import QtQuick.Layouts

RowLayout {
    id: toolbar
    required property QtObject backend
    signal focusResults()
    function focusSearch() {
        query.forceActiveFocus()
        query.selectAll()
    }
    spacing: 6
    ComboBox {
        id: history
        objectName: "searchHistory"
        Layout.fillWidth: true
        editable: true
        currentIndex: -1
        model: toolbar.backend.searchHistory
        Accessible.name: qsTr("Previous searches")
        popup.objectName: "searchHistoryPopup"
        popup.y: height
        popup.width: width
        popup.onOpened: history.popup.forceActiveFocus()
        onActivated: {
            query.text = textAt(currentIndex)
            query.forceActiveFocus()
            query.selectAll()
        }
        contentItem: TextField {
            id: query
            objectName: "searchField"
            placeholderText: qsTr("Search Everything")
            Accessible.name: qsTr("Search files and folders")
            selectByMouse: true
            focus: true
            background: null
            onTextChanged: toolbar.backend.setQuery(text)
            Keys.onDownPressed: event => {
                if (event.modifiers & Qt.AltModifier)
                    history.popup.open()
                else
                    toolbar.focusResults()
            }
            Keys.onEscapePressed: clear()
        }
    }
    ComboBox {
        id: kind
        objectName: "kindFilter"
        Layout.preferredWidth: Math.max(150, implicitContentWidth + leftPadding + rightPadding)
        implicitContentWidthPolicy: ComboBox.WidestText
        model: [qsTr("Everything"), qsTr("Files"), qsTr("Folders")]
        Accessible.name: qsTr("Result type")
        onActivated: toolbar.backend.setKind(["all", "file", "folder"][currentIndex])
    }
}
