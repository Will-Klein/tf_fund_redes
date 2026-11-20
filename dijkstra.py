"""Algoritmo de Dijkstra, implementado pelo grupo (proibido networkx, scipy etc.; heapq é permitido).

Dono: Frederico (fase F1). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.3.

Regras (enunciado, "Cálculo da tabela de roteamento", e D07):
- A LSDB define um grafo DIRIGIDO: o LSP de origem O dá as arestas O -> vizinho, com o custo indicado.
- Um nó que só aparece como vizinho dentro de algum LSP também é destino.
- Para cada destino alcançável: próximo salto = vizinho da origem pelo qual começa o caminho de
  menor custo; custo = soma dos custos. Em empate, qualquer caminho de custo mínimo serve.
"""
import heapq

def dijkstra(graph, source):
    """Calcula os caminhos mínimos a partir de 'source'.

    graph:  {nó: {vizinho: custo}}, ex.: {'10.6.1.1': {'10.6.2.1': 1}, '10.6.2.1': {'10.6.1.1': 1}}
    source: endereço virtual do próprio roteador.

    Devolve {destino: (proximo_salto, custo)}, sem incluir o próprio source.
    Se source ainda não estiver no grafo (o roteador recebeu LSPs antes de gerar o próprio),
    devolve {} sem erro.
    """
    # O roteador recebeu LSPs de outros antes de gerar o próprio: não há por onde começar.
    if source not in graph:
        return {}

    custo = {source: 0}           # menor custo conhecido até cada nó (provisório até ser finalizado)
    primeiro_salto = {}           # vizinho de source pelo qual começa o melhor caminho até cada nó
    finalizados = set()           # nós cujo menor custo já é definitivo
    fila = [(0, source)]          # fila de prioridade (heapq): (custo até o nó, nó)

    while fila:
        custo_no, no = heapq.heappop(fila)

        # A fila pode ter entradas antigas do mesmo nó (custo que depois melhorou): ignorar.
        if no in finalizados:
            continue
        finalizados.add(no)

        # Relaxamento das arestas que SAEM de 'no' (grafo dirigido, D07).
        # .get: um nó que só aparece como vizinho em algum LSP não tem LSP próprio na LSDB.
        for vizinho, peso in graph.get(no, {}).items():
            if vizinho in finalizados:
                continue
            novo_custo = custo_no + peso
            if vizinho not in custo or novo_custo < custo[vizinho]:
                custo[vizinho] = novo_custo
                # Se saímos direto do source, o próprio vizinho é o primeiro salto;
                # senão, herdamos o primeiro salto do caminho que chegou até 'no'.
                primeiro_salto[vizinho] = vizinho if no == source else primeiro_salto[no]
                heapq.heappush(fila, (novo_custo, vizinho))

    # Resultado: todos os alcançados, menos o próprio source.
    return {destino: (primeiro_salto[destino], custo[destino]) for destino in primeiro_salto}

    raise NotImplementedError("dijkstra.dijkstra: F1 (Frederico)")
