import QtQuick
import QtQuick.Controls.Fusion
import QtQuick.Layouts

Dialog {
    id: dialog
    required property QtObject backend
    objectName: "searchIndexDialog"
    title: qsTr("Search Index")
    modal: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(680, Overlay.overlay.width - 32)
    height: Math.min(540, Overlay.overlay.height - 32)
    standardButtons: Dialog.Save | Dialog.Cancel
    ListModel { id: draft }

    function containsDrive(identity) {
        for (let i = 0; i < draft.count; ++i)
            if (draft.get(i).identity === identity) return true
        return false
    }
    onOpened: {
        backend.refreshDrives()
        draft.clear()
        for (const entry of backend.catalogRoots) draft.append(entry)
        roots.currentIndex = draft.count ? 0 : -1
    }
    onAccepted: {
        let entries = []
        for (let i = 0; i < draft.count; ++i) {
            const entry = draft.get(i)
            entries.push({identity: entry.identity, root: entry.root, name: entry.name, enabled: entry.enabled})
        }
        backend.setCatalogRoots(entries)
    }
    contentItem: ColumnLayout {
        implicitHeight: 400
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            ComboBox {
                id: drives
                objectName: "availableDrives"
                Layout.fillWidth: true
                model: dialog.backend.availableDrives
                textRole: "root"
                Accessible.name: qsTr("Attached drive")
            }
            Button {
                text: qsTr("Refresh")
                onClicked: dialog.backend.refreshDrives()
            }
            Button {
                objectName: "addDrive"
                text: qsTr("Add")
                enabled: drives.currentIndex >= 0 && drives.model[drives.currentIndex].supported
                         && !dialog.containsDrive(drives.model[drives.currentIndex].identity)
                onClicked: {
                    const drive = drives.model[drives.currentIndex]
                    draft.append({identity: drive.identity, root: drive.root, name: drive.name, enabled: true})
                    roots.currentIndex = draft.count - 1
                }
            }
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            visible: drives.currentIndex >= 0 && !drives.model[drives.currentIndex].supported
            text: qsTr("This drive cannot be indexed yet. The attached drive is not supported.")
        }
        Button {
            text: qsTr("Rescan now")
            onClicked: dialog.backend.refreshIndex()
        }
        Frame {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ListView {
                id: roots
                objectName: "indexRoots"
                anchors.fill: parent
                clip: true
                model: draft
                reuseItems: true
                delegate: ItemDelegate {
                    required property var model
                    required property int index
                    width: ListView.view.width
                    text: model.name + "  —  " + model.root
                    highlighted: roots.currentIndex === index
                    onClicked: roots.currentIndex = index
                }
                ScrollBar.vertical: ScrollBar {}
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: qsTr("Name") }
            TextField {
                id: rootName
                objectName: "rootName"
                Layout.fillWidth: true
                enabled: roots.currentIndex >= 0
                text: roots.currentIndex >= 0 ? draft.get(roots.currentIndex).name : ""
                Accessible.name: qsTr("Catalog root name")
                onTextEdited: draft.setProperty(roots.currentIndex, "name", text)
            }
            CheckBox {
                objectName: "rootEnabled"
                text: qsTr("Index")
                enabled: roots.currentIndex >= 0
                checked: roots.currentIndex >= 0 && draft.get(roots.currentIndex).enabled
                onToggled: draft.setProperty(roots.currentIndex, "enabled", checked)
            }
            Button {
                objectName: "removeDrive"
                text: qsTr("Remove")
                enabled: roots.currentIndex >= 0
                onClicked: {
                    const index = roots.currentIndex
                    draft.remove(index)
                    roots.currentIndex = Math.min(index, draft.count - 1)
                }
            }
        }
    }
}
