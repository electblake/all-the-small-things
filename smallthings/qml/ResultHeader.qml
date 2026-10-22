import QtQuick
import QtQuick.Controls.Fusion

Button {
    id: heading
    required property var model
    required property int column
    required property int sortColumn
    required property bool descending
    text: model.display + (sortColumn === column ? (descending ? "  ▾" : "  ▴") : "")
    contentItem: Label {
        text: heading.text
        color: heading.palette.buttonText
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    Accessible.name: model.display
    Accessible.description: sortColumn === column
        ? (descending ? qsTr("Sorted descending") : qsTr("Sorted ascending"))
        : qsTr("Sort by this column")
}
