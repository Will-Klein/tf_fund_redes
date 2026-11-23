import itertools
import unittest

from dijkstra import dijkstra

R = lambda n: "10.6.%d.1" % n

LOCAL5 = {
    R(1): {R(2): 1, R(3): 4},
    R(2): {R(1): 1, R(3): 2, R(4): 7},
    R(3): {R(1): 4, R(2): 2, R(5): 3},
    R(4): {R(2): 7, R(5): 5},
    R(5): {R(3): 3, R(4): 5},
}


class TestDijkstra(unittest.TestCase):
    def test_local5_r1(self):
        self.assertEqual(dijkstra(LOCAL5, R(1)), {
            R(2): (R(2), 1), R(3): (R(2), 3), R(4): (R(2), 8), R(5): (R(2), 6)})

    def test_local5_r4(self):
        self.assertEqual(dijkstra(LOCAL5, R(4)), {
            R(1): (R(2), 8), R(2): (R(2), 7), R(3): (R(5), 8), R(5): (R(5), 5)})

    def test_source_fora_do_grafo(self):
        self.assertEqual(dijkstra({R(2): {R(3): 1}}, R(1)), {})

    def test_grafo_so_com_source(self):
        self.assertEqual(dijkstra({R(1): {}}, R(1)), {})

    def test_no_so_como_vizinho_e_destino(self):
        # R3 não tem LSP próprio, mas aparece na lista de R2
        self.assertEqual(dijkstra({R(1): {R(2): 1}, R(2): {R(3): 2}}, R(1)),
                         {R(2): (R(2), 1), R(3): (R(2), 3)})

    def test_aresta_so_de_ida(self):
        # R2 não lista R1: R1 ainda alcança R2, mas R2 não alcança R1
        g = {R(1): {R(2): 1}, R(2): {}}
        self.assertEqual(dijkstra(g, R(1)), {R(2): (R(2), 1)})
        self.assertEqual(dijkstra(g, R(2)), {})

    def test_sem_r2_usa_caminho_alternativo(self):
        g = {n: {v: c for v, c in viz.items() if v != R(2)}
             for n, viz in LOCAL5.items() if n != R(2)}
        self.assertEqual(dijkstra(g, R(1)), {
            R(3): (R(3), 4), R(5): (R(3), 7), R(4): (R(3), 12)})

    def test_empate_fica_com_um_caminho_de_custo_minimo(self):
        # Losango: R1 chega a R4 por R2 ou por R3, os dois com custo 2.
        # Enunciado: "em caso de empate, qualquer caminho de custo mínimo é aceito".
        g = {R(1): {R(2): 1, R(3): 1}, R(2): {R(4): 1}, R(3): {R(4): 1}, R(4): {}}
        rotas = dijkstra(g, R(1))
        self.assertEqual(rotas[R(2)], (R(2), 1))
        self.assertEqual(rotas[R(3)], (R(3), 1))
        self.assertEqual(rotas[R(4)][1], 2)
        self.assertIn(rotas[R(4)][0], (R(2), R(3)))
        # A escolha não depende da ordem em que os vizinhos aparecem no LSP
        invertido = {R(1): {R(3): 1, R(2): 1}, R(3): {R(4): 1}, R(2): {R(4): 1}, R(4): {}}
        self.assertEqual(dijkstra(invertido, R(1)), rotas)


    def test_local5_bate_com_todos_os_caminhos_e_nao_tem_empate(self):
        # Conferência sem usar o algoritmo: enumera todos os caminhos simples de cada par.
        nos = sorted(LOCAL5)
        for origem in nos:
            rotas = dijkstra(LOCAL5, origem)
            for destino in nos:
                if destino == origem:
                    continue
                caminhos = []
                meio = [n for n in nos if n not in (origem, destino)]
                for k in range(len(meio) + 1):
                    for trecho in itertools.permutations(meio, k):
                        c = [origem] + list(trecho) + [destino]
                        if all(c[i + 1] in LOCAL5[c[i]] for i in range(len(c) - 1)):
                            caminhos.append((sum(LOCAL5[c[i]][c[i + 1]] for i in range(len(c) - 1)), c[1]))
                menor = min(custo for custo, _ in caminhos)
                melhores = [salto for custo, salto in caminhos if custo == menor]
                self.assertEqual(len(melhores), 1, "empate de %s para %s" % (origem, destino))
                self.assertEqual(rotas[destino], (melhores[0], menor))


if __name__ == "__main__":
    unittest.main()
