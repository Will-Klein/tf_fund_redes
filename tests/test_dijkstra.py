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


if __name__ == "__main__":
    unittest.main()