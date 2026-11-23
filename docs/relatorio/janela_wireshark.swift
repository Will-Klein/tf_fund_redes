// Imprime o número da janela principal do Wireshark. Usado só por tira_prints.py.
import CoreGraphics
import Foundation

// Só aceita a janela visível cujo título é o arquivo pedido: o Wireshark também tem janelas auxiliares
let arquivo = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
let lista = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as! [[String: Any]]
for janela in lista where (janela[kCGWindowOwnerName as String] as? String) == "Wireshark"
    && (janela[kCGWindowLayer as String] as? Int) == 0
    && ((janela[kCGWindowName as String] as? String) ?? "").contains(arquivo) {
    print(janela[kCGWindowNumber as String] as! Int)
    break
}
