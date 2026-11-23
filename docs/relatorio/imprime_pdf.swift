// Imprime um HTML em PDF A4 com o WebKit do macOS. Usado só por gera_relatorio.py.
import Cocoa
import WebKit

// Uso: imprime <entrada.html> <saida.pdf>
let args = CommandLine.arguments
let entrada = URL(fileURLWithPath: args[1])
let saida = URL(fileURLWithPath: args[2])

class Impressor: NSObject, WKNavigationDelegate {
    var janela: NSWindow!
    var web: WKWebView!
    func iniciar() {
        let quadro = NSRect(x: 0, y: 0, width: 595, height: 842)
        janela = NSWindow(contentRect: quadro, styleMask: [.borderless], backing: .buffered, defer: false)
        web = WKWebView(frame: quadro)
        web.navigationDelegate = self
        janela.contentView = web
        web.loadFileURL(entrada, allowingReadAccessTo: entrada.deletingLastPathComponent())
    }
    func webView(_ w: WKWebView, didFinish n: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.imprimir() }
    }
    func imprimir() {
        let info = NSPrintInfo()
        info.paperSize = NSSize(width: 595.28, height: 841.89)
        info.topMargin = 54; info.bottomMargin = 54; info.leftMargin = 54; info.rightMargin = 54
        info.horizontalPagination = .fit
        info.verticalPagination = .automatic
        info.jobDisposition = .save
        info.dictionary()[NSPrintInfo.AttributeKey.jobSavingURL] = saida
        let op = web.printOperation(with: info)
        op.showsPrintPanel = false
        op.showsProgressPanel = false
        op.view?.frame = NSRect(x: 0, y: 0, width: 487, height: 734)
        op.runModal(for: janela, delegate: self, didRun: #selector(fim(_:ok:ctx:)), contextInfo: nil)
    }
    @objc func fim(_ op: NSPrintOperation, ok: Bool, ctx: UnsafeMutableRawPointer?) {
        print("impresso:", ok); exit(ok ? 0 : 1)
    }
}
let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let impressor = Impressor()
impressor.iniciar()
DispatchQueue.main.asyncAfter(deadline: .now() + 40) { print("tempo esgotado"); exit(2) }
app.run()
