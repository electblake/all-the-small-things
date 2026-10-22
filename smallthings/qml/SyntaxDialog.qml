import QtQuick
import QtQuick.Controls.Fusion

Dialog {
    title: qsTr("Search Syntax")
    modal: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(620, Overlay.overlay.width - 32)
    standardButtons: Dialog.Close
    height: Math.min(620, Overlay.overlay.height - 32)
    contentItem: ScrollView {
        id: syntaxScroll
        implicitHeight: 480
        clip: true
        ScrollBar.vertical.policy: contentHeight > availableHeight ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
        contentWidth: availableWidth
        Label {
            width: syntaxScroll.availableWidth
            wrapMode: Text.Wrap
            text: qsTr("Space = AND    | = OR    ! = NOT    < > = grouping\nUse quotes for text containing spaces. OR binds before AND.\n\n*.pdf                 PDF filenames\next:jpg;png            Multiple extensions\nfolder:projects       Folders containing projects\nsize:>10mb            Files larger than 10 MiB\ndm:today              Modified today\npath:src              Search the full path\nregex:^report.*       PCRE2 regular expression\n\nCtrl+F  Focus search     Down  Focus results\nEnter  Open     Ctrl+Enter  Open containing folder\nCtrl+Shift+C  Copy full path     Esc  Clear search")
        }
    }
}
