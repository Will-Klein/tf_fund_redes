"""Roteador de estado de enlace sobre UDP: ponto de entrada e núcleo de controle.

Dono: William. Ver docs/IMPLEMENTATION_PLAN.md §2 e §4.4.

Uso: python3 router.py <arquivo de configuração>

Threads (D02), todas usando o mesmo lock para mexer no estado:
- recepção: recvfrom() -> filtro de vizinho -> packets.parse -> handle_hello / handle_lsp / forwarder;
- temporizador: tick() a cada 0,5 s (HELLO 5 s, vizinho inativo 20 s, renovação do LSP 30 s, aging 90 s);
- principal: cli.run() lê os comandos do usuário.
A escrita no terminal fica numa thread do logger, fora do lock (D50).

Textos de log sem acento (D39).
"""

import os
import socket
import sys
import threading
import time

import cli
import config
import dijkstra
import packets
from forwarding import Forwarder
from log import Logger

# Temporizadores do enunciado (segundos)
HELLO_INTERVAL = 5      # "envia HELLO a cada 5 segundos"
NEIGHBOR_TIMEOUT = 20   # "20 segundos (4 períodos) sem enviar HELLO é considerado inativo"
LSP_REFRESH = 30        # "periodicamente, a cada 30 segundos (renovação)"
LSP_MAX_AGE = 90        # "não é renovado por 90 segundos é removido da LSDB"
TICK = 0.5              # intervalo do temporizador (D17)

TAMANHO_MAXIMO = 65535  # maior datagrama UDP possível


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
        self.last_hello_sent = None        # None: o 1º HELLO sai no primeiro tick()
        self.last_refresh = self.clock()   # a renovação de 30 s conta a partir da partida (D32)

    # ------------------------------------------------------------------ partida e threads

    def start(self):
        """Cria o socket (se não foi passado), envia o 1º HELLO e inicia as threads."""
        if self.sock is None:
            # Socket único para enviar e receber, ligado à porta configurada (RF02, D04)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("0.0.0.0", self.port))
        self.logger.log("ROTEADOR", "%s iniciado na porta UDP %d com %d vizinhos configurados"
                        % (self.address, self.port, len(self.neighbors)))
        self.tick()  # 1º HELLO já na partida
        threading.Thread(target=self.receive_loop, daemon=True).start()
        threading.Thread(target=self.timer_loop, daemon=True).start()

    def receive_loop(self):
        """Thread de recepção. Nenhum erro pode matá-la (D33)."""
        while True:
            try:
                data, peer = self.sock.recvfrom(TAMANHO_MAXIMO)
                self.handle_datagram(data, peer)
            except ConnectionResetError:
                # Só no Windows (a VM da VDI): um HELLO enviado antes a um vizinho que caiu volta
                # como "porta inalcançável", e o Windows avisa isso no recvfrom seguinte. Não é um
                # pacote nem um erro do roteador: ignorar e continuar recebendo (D44).
                continue
            except Exception as erro:
                self.logger.log("ERRO", "recepcao: %r" % erro)
                time.sleep(0.1)  # se o socket quebrar de vez, não gira sem parar

    def timer_loop(self):
        """Thread do temporizador. Nenhum erro pode matá-la (D33)."""
        while True:
            time.sleep(TICK)
            try:
                self.tick()
            except Exception as erro:
                self.logger.log("ERRO", "temporizador: %r" % erro)

    # ------------------------------------------------------------------ recepção

    def handle_datagram(self, data, peer):
        """Ponto único de entrada de um datagrama vindo de peer = (IP real, porta)."""
        with self.lock:
            # Enunciado: pacotes de um par que não está na lista de vizinhos são descartados (RF03)
            if peer not in self.neighbors:
                self.logger.log("DESCARTE", "pacote de par desconhecido %s:%d" % peer)
                return
            # Enunciado: pacotes malformados são descartados sem derrubar o roteador (RF04)
            try:
                pkt = packets.parse(data)
            except packets.MalformedPacket as erro:
                self.logger.log("DESCARTE", "pacote malformado de %s: %s" % (self.peer_name(peer), erro))
                return
            if isinstance(pkt, packets.Hello):
                self.handle_hello(pkt, peer)
            elif isinstance(pkt, packets.Lsp):
                self.handle_lsp(pkt, peer)
            else:
                self.forwarder.handle(pkt, peer)  # DADOS e ICMP

    def handle_hello(self, pkt, peer):
        """HELLO: marca o vizinho como ativo e associa o endereço virtual ao par (IP, porta)."""
        vizinho = self.neighbors[peer]
        vizinho.last_hello = self.clock()
        self.logger.log("HELLO", "HELLO recebido de %s (%s:%d)" % ((pkt.addr,) + peer), terminal=False)
        if not vizinho.active:
            vizinho.active = True
            vizinho.virtual = pkt.addr
            self.logger.log("VIZINHO", "%s (%s:%d) ficou ATIVO" % ((pkt.addr,) + peer))
            # Mudança na lista de ativos -> novo LSP imediatamente (RF08)
            self.generate_own_lsp("vizinho %s ficou ativo" % pkt.addr)
            # Sincronização: o novo vizinho recebe todos os LSPs da LSDB (RF13, D31)
            self.sync_neighbor(peer)
        elif vizinho.virtual != pkt.addr:
            # Caso raro: o mesmo par passou a anunciar outro endereço virtual (D21)
            self.logger.log("VIZINHO", "%s:%d mudou de endereco virtual: %s -> %s"
                            % (peer + (vizinho.virtual, pkt.addr)))
            vizinho.virtual = pkt.addr
            self.generate_own_lsp("vizinho mudou de endereco virtual")

    def handle_lsp(self, pkt, peer):
        """Recebimento de LSP, com as 3 regras do enunciado na ordem (RF12)."""
        de = self.peer_name(peer)
        # Regra 1: a origem é o próprio roteador -> descartar
        if pkt.origin == self.address:
            self.logger.log("LSP", "LSP descartado (propria origem): seq %d, de %s" % (pkt.seq, de))
            return
        # Regra 2: a LSDB já tem LSP dessa origem com seq maior ou igual -> descartar
        atual = self.lsdb.get(pkt.origin)
        if atual is not None and atual.seq >= pkt.seq:
            self.logger.log("LSP", "LSP descartado (copia/antigo): %s seq %d (LSDB tem seq %d), de %s"
                            % (pkt.origin, pkt.seq, atual.seq, de))
            return
        # Regra 3: substituir, reenviar a todos os ativos exceto V, e recalcular a tabela
        self.lsdb[pkt.origin] = LsdbEntry(pkt.seq, dict(pkt.neighbors), self.clock())
        self.logger.log("LSP", "LSP novo: %s seq %d [%s], de %s"
                        % (pkt.origin, pkt.seq, self.describe_neighbors(pkt.neighbors), de))
        copia = packets.encode(pkt)  # mesma origem, mesmo seq, formato exato (D35)
        for outro in self.active_peers():
            if outro != peer:
                self.send(copia, outro)
        self.recompute("LSP novo de %s" % pkt.origin)

    # ------------------------------------------------------------------ temporizador

    def tick(self):
        """Verificações periódicas do temporizador."""
        with self.lock:
            agora = self.clock()

            # HELLO a cada 5 s para todos os vizinhos CONFIGURADOS (RF05)
            if self.last_hello_sent is None or agora - self.last_hello_sent >= HELLO_INTERVAL:
                self.last_hello_sent = agora
                hello = packets.encode(packets.Hello(self.address))
                for peer in self.neighbors:
                    self.send(hello, peer)
                self.logger.log("HELLO", "HELLO enviado a %d vizinhos configurados"
                                % len(self.neighbors), terminal=False)

            # Vizinho ativo sem HELLO há 20 s -> inativo, e novo LSP imediatamente (RF07, RF08)
            for peer, vizinho in self.neighbors.items():
                if vizinho.active and agora - vizinho.last_hello >= NEIGHBOR_TIMEOUT:
                    vizinho.active = False
                    self.logger.log("VIZINHO", "%s (%s:%d) ficou INATIVO (sem HELLO ha %d s)"
                                    % ((vizinho.virtual,) + peer + (NEIGHBOR_TIMEOUT,)))
                    self.generate_own_lsp("vizinho %s ficou inativo" % vizinho.virtual)

            # Renovação periódica a cada 30 s, mesmo sem mudança (RF09, D32)
            if agora - self.last_refresh >= LSP_REFRESH:
                self.last_refresh = agora
                self.generate_own_lsp("renovacao periodica")

            # Envelhecimento: LSP de outro roteador sem renovação por 90 s é removido (RF14)
            for origem, entrada in list(self.lsdb.items()):
                if entrada.received_at is not None and agora - entrada.received_at >= LSP_MAX_AGE:
                    del self.lsdb[origem]
                    self.logger.log("LSP", "LSP de %s envelhecido (%d s sem renovacao): removido da LSDB"
                                    % (origem, LSP_MAX_AGE))
                    self.recompute("LSP de %s envelhecido" % origem)

    # ------------------------------------------------------------------ LSP próprio

    def generate_own_lsp(self, motivo):
        """Gera um novo LSP próprio, guarda na LSDB e envia a todos os vizinhos ativos (RF09-RF11)."""
        # 1º LSP: Unix time em segundos; depois, +1 a cada novo LSP (RF10, D30)
        if self.seq is None:
            self.seq = int(time.time())
        else:
            self.seq += 1
        # Só vizinhos ATIVOS entram no LSP, com o custo configurado (RF11)
        vizinhos = {v.virtual: v.cost for v in self.neighbors.values() if v.active}
        self.lsdb[self.address] = LsdbEntry(self.seq, vizinhos, None)
        dados = packets.encode(packets.Lsp(self.address, self.seq, vizinhos))
        for peer in self.active_peers():
            self.send(dados, peer)
        self.logger.log("LSP", "LSP proprio gerado (%s): seq %d [%s]"
                        % (motivo, self.seq, self.describe_neighbors(vizinhos)))
        self.recompute("LSP proprio: %s" % motivo)

    def sync_neighbor(self, peer):
        """Envia ao vizinho uma cópia de TODOS os LSPs da LSDB, inclusive o próprio (RF13, D31)."""
        for origem, entrada in self.lsdb.items():
            self.send(packets.encode(packets.Lsp(origem, entrada.seq, entrada.neighbors)), peer)
        self.logger.log("LSP", "sincronizacao: %d LSPs enviados a %s" % (len(self.lsdb), self.peer_name(peer)))

    # ------------------------------------------------------------------ tabela

    def recompute(self, motivo):
        """Recalcula a tabela com Dijkstra sobre a LSDB (RF15-RF17). Log: 1 linha (D29)."""
        grafo = {origem: entrada.neighbors for origem, entrada in self.lsdb.items()}
        rotas = dijkstra.dijkstra(grafo, self.address)
        nova = {packets.network_of(destino): (proximo, custo) for destino, (proximo, custo) in rotas.items()}
        mudou = nova != self.table
        self.routes = rotas
        self.table = nova
        if mudou:
            linhas = ["%s via %s (custo %d)" % (rede, proximo, custo)
                      for rede, (proximo, custo) in sorted(nova.items(), key=lambda item: cli.chave_endereco(item[0]))]
            self.logger.log("TABELA", "tabela recalculada (%s): MUDOU -> %s" % (motivo, "; ".join(linhas) or "vazia"))
        else:
            self.logger.log("TABELA", "tabela recalculada (%s): sem mudanca" % motivo)

    def route_for(self, dst):
        """Rota para o endereço virtual dst: (próximo salto, (IP real, porta)) ou None se não há rota."""
        with self.lock:
            rota = self.table.get(packets.network_of(dst))
            if rota is None:
                return None
            proximo = rota[0]
            for peer, vizinho in self.neighbors.items():
                if vizinho.active and vizinho.virtual == proximo:
                    return proximo, peer
            return None

    def is_local(self, addr):
        """True se addr está na rede /24 do próprio roteador."""
        return packets.same_network(addr, self.address)

    # ------------------------------------------------------------------ envio e utilidades

    def send(self, data, peer):
        """Envia bytes ao peer = (IP real, porta) pelo socket único do roteador."""
        try:
            self.sock.sendto(data, peer)
        except OSError as erro:
            self.logger.log("ERRO", "falha ao enviar para %s:%d: %s" % (peer + (erro,)))

    def active_peers(self):
        """Pares (IP real, porta) dos vizinhos ativos."""
        return [peer for peer, vizinho in self.neighbors.items() if vizinho.active]

    def peer_name(self, peer):
        """Nome legível de um vizinho para os logs: 'endereço virtual (IP:porta)'."""
        vizinho = self.neighbors.get(peer)
        if vizinho is not None and vizinho.virtual is not None:
            return "%s (%s:%d)" % ((vizinho.virtual,) + peer)
        return "%s:%d" % peer

    @staticmethod
    def describe_neighbors(vizinhos):
        """'10.6.2.1=1, 10.6.3.1=7' (ou 'sem vizinhos') para os logs."""
        return ", ".join("%s=%d" % (v, c) for v, c in vizinhos.items()) or "sem vizinhos"

    # Leitura para a CLI (devolvem cópias, feitas sob o lock)
    def get_table(self):
        """{'10.6.2.0/24': ('10.6.2.1', 1), ...}  ->  rede: (próximo salto, custo)."""
        with self.lock:
            return dict(self.table)

    def get_lsdb(self):
        """{'10.6.1.1': (1795111000, {'10.6.2.1': 1}), ...}  ->  origem: (seq, {vizinho: custo})."""
        with self.lock:
            return {origem: (e.seq, dict(e.neighbors)) for origem, e in self.lsdb.items()}

    def get_active_neighbors(self):
        """[('10.6.2.1', '192.168.0.12', 6000), ...]  ->  (endereço virtual, IP real, porta) dos ativos."""
        with self.lock:
            return [(v.virtual, ip, porta) for (ip, porta), v in self.neighbors.items() if v.active]


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 router.py <arquivo de configuracao>")
        print("Exemplo: python3 router.py configs/local5/r1.conf")
        sys.exit(1)
    try:
        cfg = config.load_config(sys.argv[1])
    except config.ConfigError as erro:
        print("Erro na configuracao:", erro)
        sys.exit(1)

    logger = Logger(os.path.join("logs", cfg.address + ".log"))
    router = Router(cfg, logger)
    router.forwarder = Forwarder(router)
    try:
        router.start()
    except OSError as erro:
        print("Erro ao abrir a porta UDP %d: %s" % (cfg.port, erro))
        sys.exit(1)
    cli.run(router, router.forwarder)
    # O log já está no arquivo e a fila do terminal já foi esvaziada (com limite de tempo). os._exit
    # encerra na hora, mesmo se o terminal estiver parado com a thread dele esperando (D50).
    os._exit(0)


if __name__ == "__main__":
    main()
