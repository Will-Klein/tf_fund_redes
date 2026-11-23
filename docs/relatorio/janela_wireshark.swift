// Imprime o número da janela principal do Wireshark. Usado só por tira_prints.py.
import CoreGraphics
import Foundation

let lista = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as! [[String: Any]]
for janela in lista where (janela[kCGWindowOwnerName as String] as? String) == "Wireshark"
    && (janela[kCGWindowLayer as String] as? Int) == 0 {
    let quadro = janela[kCGWindowBounds as String] as! [String: Any]
    if (quadro["Height"] as! Double) > 200 {
        print(janela[kCGWindowNumber as String] as! Int)
        break
    }
}
