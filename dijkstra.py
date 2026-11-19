"""Algoritmo de Dijkstra, implementado pelo grupo (proibido networkx, scipy etc.; heapq é permitido).

Dono: Frederico (fase F1). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.3.

Regras (enunciado, "Cálculo da tabela de roteamento", e D07):
- A LSDB define um grafo DIRIGIDO: o LSP de origem O dá as arestas O -> vizinho, com o custo indicado.
- Um nó que só aparece como vizinho dentro de algum LSP também é destino.
- Para cada destino alcançável: próximo salto = vizinho da origem pelo qual começa o caminho de
  menor custo; custo = soma dos custos. Em empate, qualquer caminho de custo mínimo serve.
"""


def dijkstra(graph, source):
    """Calcula os caminhos mínimos a partir de 'source'.

    graph:  {nó: {vizinho: custo}}, ex.: {'10.6.1.1': {'10.6.2.1': 1}, '10.6.2.1': {'10.6.1.1': 1}}
    source: endereço virtual do próprio roteador.

    Devolve {destino: (proximo_salto, custo)}, sem incluir o próprio source.
    Se source ainda não estiver no grafo (o roteador recebeu LSPs antes de gerar o próprio),
    devolve {} sem erro.
    """
    raise NotImplementedError("dijkstra.dijkstra: F1 (Frederico)")
