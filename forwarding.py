"""Encaminhamento de DADOS e ICMP, mensagens de erro e o comando ping.

Dono: Leonardo (fase F2). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.5.

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
"""

TTL_INICIAL = 16     # enunciado: TTL "iniciado em 16 por quem cria o pacote"
PING_TIMEOUT = 2.0   # enunciado: "ou timeout após 2 s"


class Forwarder:
    """Plano de dados do roteador. Usa do Router: address, lock, logger, route_for(), is_local(), send()."""

    def __init__(self, router):
        self.router = router
        self.next_id = 1      # id do ping: contador a partir de 1 (D19); DADOS usam id 0
        self.pending = {}     # pings esperando resposta: {id: dados do pedido}

    def send_data(self, dst, text):
        """Comando 'msg': cria e envia um DADOS. Devolve o texto a exibir ao usuário."""
        raise NotImplementedError("Forwarder.send_data: F2 (Leonardo)")

    def ping(self, dst, ttl=TTL_INICIAL):
        """Comando 'ping': envia ICMP 8 e espera até PING_TIMEOUT pela resposta (0, 11 ou 3).

        Devolve o texto a exibir: tipo da resposta, quem enviou e o RTT, ou timeout.
        """
        raise NotImplementedError("Forwarder.ping: F2 (Leonardo)")

    def handle(self, pkt, peer):
        """Trata um Dados ou Icmp recebido do vizinho 'peer' = (IP real, porta)."""
        raise NotImplementedError("Forwarder.handle: F2 (Leonardo)")
