import QtQuick
import QtQuick.Controls.Fusion
import QtQuick.Layouts

ItemDelegate {
    id: cell
    required property bool tableFocused
    signal activated(int row, int column)
    signal opened(int row, int column)
    signal contextRequested(int row, int column)
    required property var model
    required property int row
    required property int column
    required property bool selected
    required property bool current
    implicitWidth: 100
    implicitHeight: 30
    padding: 5
    text: model.display
    hoverEnabled: true
    background: Rectangle {
        color: cell.selected ? cell.palette.highlight : (cell.row % 2 ? cell.palette.alternateBase : cell.palette.base)
        border.width: cell.current && cell.tableFocused ? 1 : 0
        border.color: cell.selected ? cell.palette.highlightedText : cell.palette.highlight
    }
    contentItem: RowLayout {
        spacing: 6
        Image {
            visible: cell.column === 0
            Layout.preferredWidth: 20
            Layout.preferredHeight: 20
            source: cell.model.folder ? "icons/folder.svg" : "icons/file.svg"
            sourceSize: Qt.size(20, 20)
            Accessible.ignored: true
        }
        Label {
            id: cellLabel
            Layout.fillWidth: true
            text: cell.text
            color: cell.selected ? cell.palette.highlightedText : cell.palette.text
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: cell.column === 2 ? Text.AlignRight : Text.AlignLeft
        }
    }
    Accessible.name: cell.text
    onClicked: cell.activated(row, column)
    onDoubleClicked: cell.opened(row, column)
    ToolTip.visible: hovered && cellLabel.truncated
    ToolTip.delay: 700
    ToolTip.text: text
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: cell.contextRequested(cell.row, cell.column)
    }
}
