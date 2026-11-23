"""Interface com o usuário: lê comandos no terminal e mostra os resultados.

Dono: William. Ver docs/IMPLEMENTATION_PLAN.md §4.6.

Comandos do enunciado (<destino> é sempre um endereço virtual):
    tabela                 rede, próximo salto, custo
    lsdb                   origem, número de sequência, vizinhos e custos
    vizinhos               vizinhos ATIVOS: endereço virtual, IP real e porta
    msg <destino> <texto>  envia um pacote de dados (o texto é o resto da linha)
    ping <destino> [TTL]   pedido de eco com o TTL indicado (padrão 16); mostra a resposta
                           (eco, tempo excedido ou destino inalcançável), quem enviou e o RTT,
                           ou timeout após 2 s
Extra (D20): sair. Comando desconhecido mostra a lista acima.

Quem envia de fato é o Forwarder (forwarding.py); aqui só lemos, validamos e mostramos.
Tudo o que vai para a tela é ASCII, sem acentos (D39): funciona em qualquer terminal.
"""

import packets
from forwarding import TTL_INICIAL

AJUDA = ("Comandos: tabela | lsdb | vizinhos | msg <destino> <texto> | "
         "ping <destino> [TTL] | sair")


def chave_endereco(endereco):
    """Ordena endereços pelos números: '10.6.10.1' vem depois de '10.6.2.1'."""
    return tuple(int(parte) for parte in endereco.split("/")[0].split("."))


def formatar_tabela(tabela):
    """tabela: {rede: (próximo salto, custo)}."""
    if not tabela:
        return "Tabela vazia: nenhum roteador alcancavel."
    linhas = ["%-18s %-16s %s" % ("Rede destino", "Proximo salto", "Custo")]
    for rede in sorted(tabela, key=chave_endereco):
        proximo, custo = tabela[rede]
        linhas.append("%-18s %-16s %d" % (rede, proximo, custo))
    return "\n".join(linhas)


def formatar_lsdb(lsdb):
    """lsdb: {origem: (seq, {vizinho: custo})}."""
    if not lsdb:
        return "LSDB vazia."
    linhas = ["%-16s %-12s %s" % ("Origem", "Seq", "Vizinhos (custo)")]
    for origem in sorted(lsdb, key=chave_endereco):
        seq, vizinhos = lsdb[origem]
        lista = ", ".join("%s=%d" % (v, vizinhos[v]) for v in sorted(vizinhos, key=chave_endereco))
        linhas.append("%-16s %-12d %s" % (origem, seq, lista or "(nenhum)"))
    return "\n".join(linhas)


def formatar_vizinhos(vizinhos):
    """vizinhos: [(endereço virtual, IP real, porta)] dos vizinhos ativos."""
    if not vizinhos:
        return "Nenhum vizinho ativo."
    linhas = ["%-18s %-16s %s" % ("Endereco virtual", "IP real", "Porta")]
    for virtual, ip, porta in sorted(vizinhos, key=lambda v: chave_endereco(v[0])):
        linhas.append("%-18s %-16s %d" % (virtual, ip, porta))
    return "\n".join(linhas)


def executar(linha, router, forwarder):
    """Executa uma linha digitada. Devolve (texto para mostrar, continuar?)."""
    partes = linha.split()
    if not partes:
        return "", True
    comando = partes[0]

    if comando == "tabela" and len(partes) == 1:
        return formatar_tabela(router.get_table()), True
    if comando == "lsdb" and len(partes) == 1:
        return formatar_lsdb(router.get_lsdb()), True
    if comando == "vizinhos" and len(partes) == 1:
        return formatar_vizinhos(router.get_active_neighbors()), True
    if comando == "sair" and len(partes) == 1:
        return "Encerrando o roteador.", False

    if comando == "msg":
        # split(None, 2): o texto é todo o resto da linha, com os espaços que tiver
        partes = linha.split(None, 2)
        if len(partes) < 3:
            return "Uso: msg <destino> <texto>", True
        destino, texto = partes[1], partes[2]
        if not packets.is_virtual_addr(destino):
            return "Destino invalido: %s (use um endereco virtual, ex.: 10.6.2.1)" % destino, True
        if not packets.valid_text(texto):
            return "Texto invalido: use so caracteres ASCII (sem acentos) e sem ':'", True
        return forwarder.send_data(destino, texto), True

    if comando == "ping":
        if len(partes) not in (2, 3):
            return "Uso: ping <destino> [TTL]", True
        destino = partes[1]
        if not packets.is_virtual_addr(destino):
            return "Destino invalido: %s (use um endereco virtual, ex.: 10.6.2.1)" % destino, True
        ttl = TTL_INICIAL
        if len(partes) == 3:
            if not packets.so_digitos(partes[2]) or int(partes[2]) < 1:
                return "TTL invalido: %s (use um inteiro >= 1)" % partes[2], True
            ttl = int(partes[2])
        return forwarder.ping(destino, ttl), True

    return "Comando desconhecido. " + AJUDA, True


def run(router, forwarder):
    """Laço principal: lê uma linha por vez até 'sair' (ou Ctrl+C / fim da entrada)."""
    print("Roteador %s pronto. %s" % (router.address, AJUDA))
    while True:
        try:
            linha = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            texto, continuar = executar(linha, router, forwarder)
        except KeyboardInterrupt:
            # Ctrl+C durante a espera de um ping: encerra limpo, como no input acima (D48)
            print()
            break
        except Exception as erro:
            # Um erro num comando não pode derrubar o roteador (D38)
            texto, continuar = "Erro ao executar o comando: %s" % erro, True
        if texto:
            print(texto)
        if not continuar:
            break
