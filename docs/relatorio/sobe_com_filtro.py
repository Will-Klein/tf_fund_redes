"""Sobe um roteador REAL com uma falha de rede simulada (só para os experimentos Q5 e Q6).

O código do roteador não muda: aqui o socket é embrulhado e alguns datagramas recebidos são jogados
fora, como se tivessem se perdido na rede. Cada descarte é anotado em falhas_injetadas.txt.

Uso: python3 sobe_com_filtro.py <arquivo .conf> <regra>
Regras:
  q5           depois que o arquivo 'arma_perda' existir, perde todas as cópias do primeiro LSP
               do R5 que já não lista o R4
  q6_corte:P   depois que o arquivo 'corta_enlace' existir, perde tudo o que vem da porta P
  q6_atraso    entre os arquivos 'corta_enlace' e 'libera_lsp', perde os LSPs do R2 sem o R1
"""

import os
import socket
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

import cli                        # noqa: E402
import config                     # noqa: E402
import packets                    # noqa: E402
import router                     # noqa: E402
from forwarding import Forwarder  # noqa: E402
from log import Logger            # noqa: E402

R1, R2, R4, R5 = "10.6.1.1", "10.6.2.1", "10.6.4.1", "10.6.5.1"


def ler_lsp(dados):
    """Devolve o Lsp contido nos bytes, ou None se for outro tipo de pacote."""
    try:
        pacote = packets.parse(dados)
    except packets.MalformedPacket:
        return None
    return pacote if isinstance(pacote, packets.Lsp) else None


class RegraQ5:
    """Perde todas as cópias de um único LSP: o primeiro do R5 sem o R4."""

    def __init__(self):
        self.seq_perdido = None

    def __call__(self, dados, peer):
        if not os.path.exists("arma_perda"):   # não vale a partida, quando o R4 ainda não está ativo
            return False
        lsp = ler_lsp(dados)
        if lsp is None or lsp.origin != R5 or R4 in lsp.neighbors:
            return False
        if self.seq_perdido is None:
            self.seq_perdido = lsp.seq
        return lsp.seq == self.seq_perdido


def regra_corte(porta):
    """Enlace cortado: depois do arquivo 'corta_enlace', nada que venha dessa porta é recebido."""
    return lambda dados, peer: peer[1] == porta and os.path.exists("corta_enlace")


def regra_atraso(dados, peer):
    """LSP atrasado: enquanto não existir 'libera_lsp', o R3 não vê o LSP novo do R2."""
    if not os.path.exists("corta_enlace") or os.path.exists("libera_lsp"):
        return False
    lsp = ler_lsp(dados)
    return lsp is not None and lsp.origin == R2 and R1 not in lsp.neighbors


class SocketComFalha:
    """Mesmo uso de um socket, mas recvfrom() pula os datagramas que a regra mandar perder."""

    def __init__(self, real, regra, nome):
        self.real = real
        self.regra = regra
        self.nome = nome

    def recvfrom(self, tamanho):
        while True:
            dados, peer = self.real.recvfrom(tamanho)
            if not self.regra(dados, peer):
                return dados, peer
            with open("falhas_injetadas.txt", "a", encoding="ascii") as arquivo:
                arquivo.write("%.3f %s perdeu de %s:%d: %s\n"
                              % (time.time(), self.nome, peer[0], peer[1], dados.decode("ascii", "replace")))

    def sendto(self, dados, peer):
        return self.real.sendto(dados, peer)


def main():
    cfg = config.load_config(sys.argv[1])
    nome_regra = sys.argv[2]
    if nome_regra == "q5":
        regra = RegraQ5()
    elif nome_regra == "q6_atraso":
        regra = regra_atraso
    else:
        regra = regra_corte(int(nome_regra.split(":")[1]))

    real = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    real.bind(("0.0.0.0", cfg.port))
    logger = Logger(os.path.join("logs", cfg.address + ".log"))
    roteador = router.Router(cfg, logger, sock=SocketComFalha(real, regra, cfg.address))
    roteador.forwarder = Forwarder(roteador)
    roteador.start()
    cli.run(roteador, roteador.forwarder)


if __name__ == "__main__":
    main()
