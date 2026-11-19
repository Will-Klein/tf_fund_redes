"""Roteador de estado de enlace sobre UDP: ponto de entrada e núcleo de controle.

Dono: William (fases F1 e F2). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §2 e §4.4.

Uso: python3 router.py <arquivo de configuração>

Threads (D02), todas usando o mesmo lock para mexer no estado:
- recepção: recvfrom() -> filtro de vizinho -> packets.parse -> handle_hello / handle_lsp / forwarder;
- temporizador: tick() a cada 0,5 s (HELLO 5 s, vizinho inativo 20 s, renovação do LSP 30 s, aging 90 s);
- principal: cli.run() lê os comandos do usuário.
"""

import os
import sys
import threading
import time

import cli
import config
from forwarding import Forwarder
from log import Logger

# Temporizadores do enunciado (segundos)
HELLO_INTERVAL = 5      # "envia HELLO a cada 5 segundos"
NEIGHBOR_TIMEOUT = 20   # "20 segundos (4 períodos) sem enviar HELLO é considerado inativo"
LSP_REFRESH = 30        # "periodicamente, a cada 30 segundos (renovação)"
LSP_MAX_AGE = 90        # "não é renovado por 90 segundos é removido da LSDB"
TICK = 0.5              # intervalo do temporizador (D17)


class Neighbor:
    """Estado de um vizinho do arquivo de configuração."""

    def __init__(self, cost):
        self.cost = cost         # custo do enlace (configuração)
        self.virtual = None      # endereço virtual, aprendido pelo HELLO
        self.active = False      # True depois do 1º HELLO; False após 20 s sem HELLO
        self.last_hello = None   # instante (relógio monotônico) do último HELLO recebido


class LsdbEntry:
    """Um LSP guardado na LSDB."""

    def __init__(self, seq, neighbors, received_at):
        self.seq = seq                  # número de sequência
        self.neighbors = neighbors      # {endereço virtual do vizinho: custo}
        self.received_at = received_at  # quando foi aceito (None no LSP próprio, que não envelhece)


class Router:
    def __init__(self, cfg, logger, sock=None, clock=time.monotonic):
        """cfg: config.Config. sock e clock podem ser trocados por falsos nos testes."""
        self.address = cfg.address
        self.port = cfg.port
        self.logger = logger
        self.sock = sock
        self.clock = clock
        self.lock = threading.RLock()
        self.neighbors = {(n.ip, n.port): Neighbor(n.cost) for n in cfg.neighbors}
        self.lsdb = {}         # {origem: LsdbEntry}
        self.seq = None        # último seq próprio usado; None até o 1º LSP (D30)
        self.routes = {}       # {roteador destino: (próximo salto, custo)}, saída do Dijkstra
        self.table = {}        # {'10.G.R.0/24': (próximo salto, custo)}
        self.forwarder = None  # Forwarder, ligado em main()

    def start(self):
        """Cria o socket (se não foi passado), envia o 1º HELLO e inicia as threads."""
        raise NotImplementedError("Router.start: F1 (William)")

    def handle_datagram(self, data, peer):
        """Ponto único de entrada de um datagrama vindo de peer = (IP real, porta)."""
        raise NotImplementedError("Router.handle_datagram: F1 (William)")

    def tick(self):
        """Verificações periódicas do temporizador."""
        raise NotImplementedError("Router.tick: F1/F2 (William)")

    def route_for(self, dst):
        """Rota para o endereço virtual dst: (próximo salto, (IP real, porta)) ou None se não há rota."""
        raise NotImplementedError("Router.route_for: F2 (William)")

    def is_local(self, addr):
        """True se addr está na rede /24 do próprio roteador."""
        raise NotImplementedError("Router.is_local: F1 (William)")

    def send(self, data, peer):
        """Envia bytes ao peer = (IP real, porta) pelo socket único do roteador."""
        raise NotImplementedError("Router.send: F1 (William)")

    # Leitura para a CLI (devolvem cópias, feitas sob o lock)
    def get_table(self):
        raise NotImplementedError("Router.get_table: F2 (William)")

    def get_lsdb(self):
        raise NotImplementedError("Router.get_lsdb: F2 (William)")

    def get_active_neighbors(self):
        raise NotImplementedError("Router.get_active_neighbors: F1 (William)")


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 router.py <arquivo de configuração>")
        print("Exemplo: python3 router.py configs/local5/r1.conf")
        sys.exit(1)
    try:
        cfg = config.load_config(sys.argv[1])
    except config.ConfigError as erro:
        print("Erro na configuração:", erro)
        sys.exit(1)

    logger = Logger(os.path.join("logs", cfg.address + ".log"))
    router = Router(cfg, logger)
    router.forwarder = Forwarder(router)
    router.start()
    cli.run(router, router.forwarder)


if __name__ == "__main__":
    main()
