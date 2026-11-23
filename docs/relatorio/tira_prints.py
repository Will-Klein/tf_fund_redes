"""Tira os prints reais do Wireshark usados no relatório (figuras/wireshark_q2.png a q6.png).

Abre cada captura .pcapng no Wireshark, aplica o filtro de exibição e fotografa a janela. Usa um perfil
temporário, então as preferências do Wireshark instalado não mudam. Os filtros saem das medições, para
os prints continuarem certos se os experimentos forem refeitos.

Só funciona no macOS, com o Wireshark instalado e permissão de Gravação de Tela.
Uso, da raiz do repositório: python3 docs/relatorio/tira_prints.py
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
WIRESHARK = "/Applications/Wireshark.app/Contents/MacOS/Wireshark"
TSHARK = shutil.which("tshark") or "/Applications/Wireshark.app/Contents/MacOS/tshark"

PREFERENCIAS = """gui.column.format:
\t"No.", "%m",
\t"Tempo (s)", "%Rt",
\t"Porta origem", "%uS",
\t"Porta destino", "%uD",
\t"Protocolo", "%p",
\t"Tam.", "%L",
\t"Conteudo do pacote", "%Cus:data.text:0:R"
data.show_as_text: TRUE
gui.update.enabled: FALSE
gui.ask_unsaved: FALSE
"""
RECENTES = "gui.packet_list_show: TRUE\ngui.tree_view_show: FALSE\ngui.byte_view_show: FALSE\n"


def ler(nome):
    with open(os.path.join(AQUI, "evidencias", nome, "resultado.json"), encoding="utf-8") as arquivo:
        return json.load(arquivo)


def assinatura(captura):
    """SHA-256 da captura: permite saber se um print foi tirado exatamente deste arquivo."""
    with open(os.path.join(AQUI, "capturas", captura + ".pcapng"), "rb") as arquivo:
        return hashlib.sha256(arquivo.read()).hexdigest()


def casos():
    """{chave: (captura, filtro de exibição)}, com os números de sequência reais de cada experimento."""
    q2 = ler("q2_inundacao")["filtro"]
    gerados = []
    for n in (1, 3, 4):
        caminho = os.path.join(AQUI, "evidencias", "q3_convergencia_1", "logs_roteadores", "10.6.%d.1.log" % n)
        with open(caminho, encoding="ascii") as arquivo:
            for seq in re.findall(r"LSP proprio gerado \(vizinho 10\.6\.2\.1 ficou inativo\): seq (\d+)", arquivo.read()):
                gerados.append('udp contains "LSP:10.6.%d.1:%s"' % (n, seq))
    # Só as duas últimas rodadas de HELLO do R2 (3 vizinhos cada): mostram que eles param
    hellos = subprocess.run([TSHARK, "-r", os.path.join(AQUI, "capturas", "q3_convergencia_1.pcapng"), "-Y",
                             'udp.srcport == 6002 and udp contains "HELLO"', "-T", "fields", "-e", "frame.number"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True, check=True).stdout.split()
    q3 = '(udp.srcport == 6002 and udp contains "HELLO" and frame.number >= %s) or ' % hellos[-6] + " or ".join(gerados)
    q4 = " or ".join('udp contains "LSP:10.6.2.1:%d:"' % s for s in range(4))
    r5 = ler("q5_confiabilidade")
    perdido = r5["copias_perdidas_pelo_r1"][0].split()[-1].split(":")[2]
    recuperou = r5["lsp_que_recuperou"].split()[4]
    q5 = 'udp contains "LSP:10.6.5.1:%s" or udp contains "LSP:10.6.5.1:%s"' % (perdido, recuperou)
    q6 = '(udp contains "ICMP:10.6.5.1:10.6.1.1" and udp contains ":1:8") or udp contains "ICMP:10.6.2.1:10.6.5.1"'
    return {"q2": ("q2_inundacao", q2), "q3": ("q3_convergencia_1", q3), "q4": ("q4_sequencia", q4),
            "q5": ("q5_confiabilidade", q5), "q6": ("q6_ttl_laco", q6)}


def main():
    if subprocess.run(["pgrep", "-x", "Wireshark"], stdout=subprocess.DEVNULL).returncode == 0:
        sys.exit("Feche o Wireshark antes de tirar os prints.")
    caminho_registro = os.path.join(AQUI, "figuras", "prints.json")
    if os.path.exists(caminho_registro):
        os.remove(caminho_registro)   # o registro só volta a existir se os 5 prints saírem certos
    pasta = tempfile.mkdtemp(prefix="prints_wireshark_")
    try:
        with open(os.path.join(pasta, "preferences"), "w") as arquivo:
            arquivo.write(PREFERENCIAS)
        with open(os.path.join(pasta, "recent"), "w") as arquivo:
            arquivo.write(RECENTES)
        localizador = os.path.join(pasta, "janela")
        subprocess.run(["swiftc", "-O", os.path.join(AQUI, "janela_wireshark.swift"), "-o", localizador], check=True)
        ambiente = dict(os.environ, WIRESHARK_CONFIG_DIR=pasta)
        registro = {}
        for chave, (captura, filtro) in casos().items():
            processo = subprocess.Popen([WIRESHARK, "-r", os.path.join(AQUI, "capturas", captura + ".pcapng"), "-Y", filtro],
                                        env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            janela = ""
            for _ in range(120):
                time.sleep(0.25)
                janela = subprocess.run([localizador, captura + ".pcapng"], stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
                if janela:
                    break
            time.sleep(2.2)
            saida = os.path.join(AQUI, "figuras", "wireshark_%s.png" % chave)
            try:
                subprocess.run(["screencapture", "-x", "-o", "-l", janela, saida], check=True)
            finally:
                processo.terminate()     # fecha o Wireshark mesmo se o print falhar
                processo.wait(timeout=8)
            time.sleep(2.5)
            from PIL import Image
            if Image.open(saida).size[0] < 1800:   # janela errada: não pode virar evidência
                sys.exit("O print %s nao capturou a janela principal do Wireshark." % chave)
            registro[chave] = {"captura": captura, "sha256": assinatura(captura), "filtro": filtro}
            print("%s: %s" % (chave, os.path.relpath(saida)), flush=True)
        # Só grava o registro se os 5 prints saíram: é ele que libera a geração do PDF
        with open(caminho_registro, "w", encoding="utf-8") as arquivo:
            json.dump(registro, arquivo, indent=2, ensure_ascii=False)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    main()
