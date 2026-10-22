import QtQuick
import QtQuick.Controls.Fusion
import QtQuick.Layouts

Dialog {
    id: dialog
    required property QtObject backend
    objectName: "indexIssuesDialog"
    title: qsTr("Indexing report")
    modal: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(800, Overlay.overlay.width - 32)
    height: Math.min(540, Overlay.overlay.height - 32)
    standardButtons: Dialog.Close
    contentItem: ScrollView {
        ListView {
            clip: true
            model: dialog.backend.indexIssues
            delegate: ItemDelegate {
                required property var modelData
                width: ListView.view.width
                text: modelData.path + "\n" + modelData.reason
                onClicked: reportText.text = text
            }
        }
    }
    footer: ColumnLayout {
        TextArea {
            id: reportText
            Layout.fillWidth: true
            readOnly: true
            wrapMode: TextEdit.WrapAnywhere
            placeholderText: qsTr("Select an entry to read or copy its details.")
        }
        DialogButtonBox {
            Layout.fillWidth: true
            standardButtons: Dialog.Close
            onRejected: dialog.reject()
        }
    }
}
