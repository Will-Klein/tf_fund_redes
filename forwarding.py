"""Encaminhamento de DADOS e ICMP, mensagens de erro e o comando ping.

Dono: Frederico (fase F2). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.5.

Regras (enunciado, "Encaminhamento"):

Ao originar um pacote (DADOS ou ICMP):
  consultar a tabela; sem rota para a rede do destino -> informar "destino inalcançável" ao usuário,
  sem enviar nada; com rota -> enviar com o TTL inicial ao (IP real, porta) do próximo salto.
  Destino na própria rede: o pacote vai direto para handle(), como se tivesse chegado (D09).

Ao receber um pacote DADOS ou ICMP:
  1. destino na própria rede (10.G.R.0/24) -> entregue ao próprio roteador:
     DADOS  -> exibir origem, destino e mensagem;
     ICMP 8 -> responder ICMP 0 para a origem, mesmo id; origem da resposta = destino do pedido;
     ICMP 0, 11 ou 3 -> exibir o resultado ao usuário (e acordar o ping pendente com esse id).
  2. destino em outra rede:
     decrementar o TTL; se chegar a 0 (<= 0, D14) -> descartar e enviar ICMP 11 para a origem;
     sem rota -> descartar e enviar ICMP 3 para a origem;
     senão -> encaminhar ao próximo salto com o novo TTL (log com próximo salto e TTL).

Erros 11 e 3 gerados pelo roteador: origem = endereço do próprio roteador, TTL 16, id do pacote que
causou o erro. NUNCA gerar erro (11 ou 3) em resposta a outra mensagem de erro (D10).
Pacote gerado pelo roteador (resposta 0, erro 11/3) sem rota de volta: não envia, só log (D11).

Textos para o usuário (D40: contrato com cli.py e tests/integration_local.py; ASCII, sem acento, D39).
Começo fixo; o resto da linha é livre:
    ping, resposta tipo 0:   "Resposta de eco de <origem> (id=7) RTT=1.23 ms"
    ping, resposta tipo 11:  "Tempo excedido informado por <origem> (id=7) RTT=0.84 ms"
    ping, resposta tipo 3:   "Destino inalcancavel informado por <origem> (id=7) RTT=0.90 ms"
    ping, sem resposta:      "Timeout: nenhuma resposta em 2 s (id=7)"
    msg/ping sem rota:       "Destino inalcancavel: sem rota para 10.6.9.0/24 (nada foi enviado)"
    msg enviada:             "DADOS enviado para <destino> via <proximo salto>"
    DADOS recebido:          "Mensagem de <origem> para <destino>: <texto>"

Como o texto chega ao usuário:
- msg e ping: o texto é o valor devolvido (a CLI imprime);
- o que chega pela rede (DADOS recebido, resposta atrasada de ping): handle() imprime na hora
  (D46), e a linha também vai para o arquivo de log.
"""

import threading
import time

import packets

TTL_INICIAL = 16     # enunciado: TTL "iniciado em 16 por quem cria o pacote"
PING_TIMEOUT = 2.0   # enunciado: "ou timeout após 2 s"

# Erros ICMP: nunca geram outro erro (enunciado: "nunca se gera mensagem de erro em resposta a outra")
TIPOS_DE_ERRO = (packets.ICMP_TIME_EXCEEDED, packets.ICMP_DEST_UNREACHABLE)

NOMES_ICMP = {packets.ICMP_ECHO_REPLY: "resposta de eco",
              packets.ICMP_DEST_UNREACHABLE: "destino inalcancavel",
              packets.ICMP_ECHO_REQUEST: "pedido de eco",
              packets.ICMP_TIME_EXCEEDED: "tempo excedido"}

# Começo fixo do texto de cada resposta do ping (D40)
ROTULOS_RESPOSTA = {packets.ICMP_ECHO_REPLY: "Resposta de eco de",
                    packets.ICMP_TIME_EXCEEDED: "Tempo excedido informado por",
                    packets.ICMP_DEST_UNREACHABLE: "Destino inalcancavel informado por"}

PROPRIA_REDE = "propria rede"   # valor devolvido por emitir() quando o destino é a própria /24


def descrever(pkt):
    """Texto curto de um pacote para os logs."""
    if isinstance(pkt, packets.Dados):
        return "DADOS %s -> %s" % (pkt.src, pkt.dst)
    return "ICMP tipo %d (%s) %s -> %s (id=%d)" % (
        pkt.type, NOMES_ICMP.get(pkt.type, "?"), pkt.src, pkt.dst, pkt.id)


def texto_resultado(pkt, rtt):
    """Texto de uma resposta ICMP 0, 11 ou 3. rtt em ms, ou None se não há ping pendente."""
    texto = "%s %s (id=%d)" % (ROTULOS_RESPOSTA[pkt.type], pkt.src, pkt.id)
    if rtt is None:
        return texto + " (sem ping pendente)"
    return texto + " RTT=%.2f ms" % rtt


class Forwarder:
    """Plano de dados do roteador. Usa do Router: address, lock, logger, route_for(), is_local(), send()."""

    def __init__(self, router):
        self.router = router
        self.next_id = 1      # id do ping: contador a partir de 1 (D19); DADOS usam id 0
        self.pending = {}     # pings esperando resposta: {id: {"evento", "inicio", "resposta"}}

    # ------------------------------------------------------------------ comandos do usuário

    def send_data(self, dst, text):
        """Comando 'msg': cria e envia um DADOS. Devolve o texto a exibir ao usuário."""
        with self.router.lock:
            pkt = packets.Dados(self.router.address, dst, TTL_INICIAL, 0, text)
            proximo = self.emitir(pkt)
            if proximo is None:
                return self.sem_rota(dst)
            if proximo == PROPRIA_REDE:
                return "DADOS entregue ao proprio roteador (%s)" % dst
            return "DADOS enviado para %s via %s" % (dst, proximo)

    def ping(self, dst, ttl=TTL_INICIAL):
        """Comando 'ping': envia ICMP 8 e espera até PING_TIMEOUT pela resposta (0, 11 ou 3).

        Devolve o texto a exibir: tipo da resposta, quem enviou e o RTT, ou timeout.
        """
        # 1. Registra o pedido pendente e envia, tudo dentro do lock (a resposta só é tratada
        #    depois, pela thread de recepção, quando o pedido já está em self.pending).
        with self.router.lock:
            ident = self.next_id
            self.next_id += 1
            pedido = {"evento": threading.Event(), "inicio": time.perf_counter(), "resposta": None}
            self.pending[ident] = pedido
            pkt = packets.Icmp(self.router.address, dst, ttl, ident, packets.ICMP_ECHO_REQUEST)
            if self.emitir(pkt) is None:
                del self.pending[ident]
                return self.sem_rota(dst)

        # 2. Espera FORA do lock: se esperasse dentro, a thread de recepção não conseguiria
        #    entrar para entregar a resposta e o ping sempre daria timeout.
        pedido["evento"].wait(PING_TIMEOUT)

        # 3. Lê o resultado sob o lock (a resposta pode chegar no último instante).
        with self.router.lock:
            self.pending.pop(ident, None)
            resposta = pedido["resposta"]
        if resposta is None:
            self.router.logger.log("ICMP", "ping id=%d para %s: timeout" % (ident, dst))
            return "Timeout: nenhuma resposta em %g s (id=%d)" % (PING_TIMEOUT, ident)
        pkt_resposta, rtt = resposta
        return texto_resultado(pkt_resposta, rtt)

    # ------------------------------------------------------------------ pacote vindo da rede

    def handle(self, pkt, peer):
        """Trata um Dados ou Icmp recebido do vizinho 'peer' = (IP real, porta).

        peer é None quando o pacote foi criado aqui mesmo para a própria rede (D09).
        """
        with self.router.lock:
            if self.router.is_local(pkt.dst):
                self.entregar(pkt)
            else:
                self.em_transito(pkt)

    def entregar(self, pkt):
        """Destino na própria rede: o pacote é do próprio roteador."""
        log = self.router.logger.log
        if isinstance(pkt, packets.Dados):
            self.mostrar("Mensagem de %s para %s: %s" % (pkt.src, pkt.dst, pkt.msg))
        elif pkt.type == packets.ICMP_ECHO_REQUEST:
            log("ENTREGA", "pedido de eco entregue ao roteador: %s" % descrever(pkt))
            # Resposta: origem = endereço que foi "pingado" (pkt.dst), destino = quem pingou,
            # mesmo id, TTL inicial (enunciado, regra 3 do recebimento).
            resposta = packets.Icmp(pkt.dst, pkt.src, TTL_INICIAL, pkt.id, packets.ICMP_ECHO_REPLY)
            if self.emitir(resposta) is None:
                log("DESCARTE", "resposta de eco para %s sem rota de volta: nada foi enviado (id=%d)"
                    % (pkt.src, pkt.id))
        else:
            self.resultado_icmp(pkt)   # tipos 0, 11 e 3

    def resultado_icmp(self, pkt):
        """ICMP 0, 11 ou 3 entregue ao roteador: acorda o ping pendente ou, se não há, exibe."""
        pedido = self.pending.get(pkt.id)
        if pedido is not None and pedido["resposta"] is None:
            rtt = (time.perf_counter() - pedido["inicio"]) * 1000
            pedido["resposta"] = (pkt, rtt)
            pedido["evento"].set()
            self.router.logger.log("ENTREGA", "resposta de ping entregue: %s" % descrever(pkt))
        else:
            self.mostrar(texto_resultado(pkt, None))   # resposta atrasada ou de um msg (D18)

    def em_transito(self, pkt):
        """Destino em outra rede: decrementa o TTL e encaminha, ou descarta com erro ICMP."""
        log = self.router.logger.log
        # 1. TTL primeiro (a ordem é a do enunciado): chegou a 0 -> descarta e avisa a origem (11)
        novo_ttl = pkt.ttl - 1
        if novo_ttl <= 0:   # <= 0 e não == 0: cobre pacote que chega com TTL 0 (D14)
            log("DESCARTE", "%s descartado: TTL chegou a 0" % descrever(pkt))
            self.gerar_erro(pkt, packets.ICMP_TIME_EXCEEDED)
            return
        # 2. Depois, a rota: sem rota -> descarta e avisa a origem (3)
        rota = self.router.route_for(pkt.dst)
        if rota is None:
            log("DESCARTE", "%s descartado: sem rota para %s"
                % (descrever(pkt), packets.network_of(pkt.dst)))
            self.gerar_erro(pkt, packets.ICMP_DEST_UNREACHABLE)
            return
        # 3. Encaminha com o novo TTL ao (IP real, porta) do próximo salto
        proximo, destino_real = rota
        self.router.send(packets.encode(pkt._replace(ttl=novo_ttl)), destino_real)
        log("ENCAMINHA", "%s encaminhado ao proximo salto %s, TTL %d" % (descrever(pkt), proximo, novo_ttl))

    # ------------------------------------------------------------------ apoio

    def emitir(self, pkt):
        """Coloca na rede um pacote que ESTE roteador criou. Devolve:
        PROPRIA_REDE se o destino é a própria /24 (entregue direto, D09);
        o endereço virtual do próximo salto, se enviou; ou None se não há rota (nada foi enviado).
        """
        if self.router.is_local(pkt.dst):
            self.registrar_geracao(pkt, "entrega local")
            self.handle(pkt, None)
            return PROPRIA_REDE
        rota = self.router.route_for(pkt.dst)
        if rota is None:
            return None
        proximo, destino_real = rota
        self.registrar_geracao(pkt, "via %s" % proximo)
        self.router.send(packets.encode(pkt), destino_real)
        return proximo

    def gerar_erro(self, causa, tipo):
        """Envia à origem de 'causa' um ICMP de erro (11 ou 3), a não ser que 'causa' seja um erro."""
        log = self.router.logger.log
        if isinstance(causa, packets.Icmp) and causa.type in TIPOS_DE_ERRO:
            log("DESCARTE", "nenhum erro gerado: o pacote descartado ja era um erro (%s)" % descrever(causa))
            return
        # Erro: origem = este roteador, TTL 16, id copiado do pacote que causou o erro
        erro = packets.Icmp(self.router.address, causa.src, TTL_INICIAL, causa.id, tipo)
        if self.emitir(erro) is None:
            log("DESCARTE", "erro ICMP tipo %d para %s sem rota de volta: nada foi enviado (D11)"
                % (tipo, causa.src))

    def registrar_geracao(self, pkt, detalhe):
        """Log de um pacote criado aqui: ICMP gerado (RF24) ou DADOS enviado."""
        if isinstance(pkt, packets.Icmp):
            self.router.logger.log("ICMP", "gerado: %s, TTL %d, %s" % (descrever(pkt), pkt.ttl, detalhe))
        else:
            self.router.logger.log("ENCAMINHA", "enviado: %s, TTL %d, %s" % (descrever(pkt), pkt.ttl, detalhe))

    def sem_rota(self, dst):
        """Texto e log de 'sem rota' ao originar (nada é enviado)."""
        rede = packets.network_of(dst)
        self.router.logger.log("DESCARTE", "sem rota para %s: nada foi enviado" % rede)
        return "Destino inalcancavel: sem rota para %s (nada foi enviado)" % rede

    def mostrar(self, texto):
        """Exibe um texto ao usuário (terminal) e o registra só no arquivo de log (D46)."""
        self.router.logger.log("ENTREGA", texto, terminal=False)
        print(texto, flush=True)