"""Interface com o usuário: lê comandos no terminal e mostra os resultados.

Dono: William (fase F2). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.6.

Comandos do enunciado (<destino> é sempre um endereço virtual):
    tabela                 rede, próximo salto, custo
    lsdb                   origem, número de sequência, vizinhos e custos
    vizinhos               vizinhos ATIVOS: endereço virtual, IP real e porta
    msg <destino> <texto>  envia um pacote de dados (o texto é o resto da linha)
    ping <destino> [TTL]   pedido de eco com o TTL indicado (padrão 16); mostra a resposta
                           (eco, tempo excedido ou destino inalcançável), quem enviou e o RTT,
                           ou timeout após 2 s
Extra (D20): sair. Comando desconhecido mostra a lista acima.
"""


def run(router, forwarder):
    """Laço principal: lê uma linha por vez até 'sair' (ou Ctrl+C / fim da entrada)."""
    raise NotImplementedError("cli.run: F2 (William)")
