import QtQuick
import QtQuick.Controls
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
    TextField {
        id: query
        objectName: "searchField"
        Layout.fillWidth: true
        placeholderText: qsTr("Search Everything")
        Accessible.name: qsTr("Search files and folders")
        selectByMouse: true
        focus: true
        onTextChanged: toolbar.backend.setQuery(text)
        Keys.onDownPressed: toolbar.focusResults()
        Keys.onEscapePressed: clear()
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
