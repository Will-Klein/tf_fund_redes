"""Testes do router.py (dono: William): vizinhança, LSP, inundação, sincronização, envelhecimento e tabela.

O Router roda sem rede: socket falso (guarda o que foi enviado) e relógio falso (avança à mão).
"""

import time
import unittest

import config
import packets
import router
from router import Router

# R1 de um anel de 4 roteadores usado só nos testes (R1-R2=1, R2-R4=2, R4-R3=3, R3-R1=7)
R2 = ("127.0.0.1", 6002)   # 10.6.2.1, custo 1
R3 = ("127.0.0.1", 6003)   # 10.6.3.1, custo 7
DESCONHECIDO = ("127.0.0.1", 6999)


class SocketFalso:
    def __init__(self):
        self.enviados = []   # [(bytes, peer)]

    def sendto(self, data, peer):
        self.enviados.append((data, peer))

    def para(self, peer):
        return [packets.parse(d) for d, p in self.enviados if p == peer]

    def limpar(self):
        self.enviados = []


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class LoggerFalso:
    def __init__(self):
        self.linhas = []   # [(categoria, texto)]

    def log(self, categoria, texto, terminal=True):
        self.linhas.append((categoria, texto))

    def tem(self, categoria, trecho):
        return any(c == categoria and trecho in t for c, t in self.linhas)


class ForwarderFalso:
    def __init__(self):
        self.recebidos = []

    def handle(self, pkt, peer):
        self.recebidos.append((pkt, peer))


def criar_r1():
    cfg = config.Config("10.6.1.1", 6001, [config.NeighborConf("127.0.0.1", 6002, 1),
                                           config.NeighborConf("127.0.0.1", 6003, 7)])
    sock, relogio, logger = SocketFalso(), Relogio(), LoggerFalso()
    r = Router(cfg, logger, sock=sock, clock=relogio)
    r.forwarder = ForwarderFalso()
    return r, sock, relogio, logger


def hello(r, peer, endereco):
    r.handle_datagram(("HELLO:%s" % endereco).encode(), peer)


def lsp(r, peer, origem, seq, vizinhos):
    lista = ";".join("%s=%d" % (v, c) for v, c in vizinhos.items())
    r.handle_datagram(("LSP:%s:%d:%s" % (origem, seq, lista)).encode(), peer)


class TestFiltroDeVizinho(unittest.TestCase):
    """O descarte de par desconhecido acontece antes da leitura do pacote."""

    def test_par_desconhecido_e_descartado_sem_mudar_nada(self):
        r, sock, _, logger = criar_r1()
        r.handle_datagram(b"HELLO:10.6.9.1", DESCONHECIDO)
        r.handle_datagram(b"LSP:10.6.9.1:5:10.6.1.1=1", DESCONHECIDO)
        self.assertEqual(sock.enviados, [])
        self.assertEqual(r.lsdb, {})
        self.assertFalse(any(v.active for v in r.neighbors.values()))
        self.assertTrue(logger.tem("DESCARTE", "par desconhecido 127.0.0.1:6999"))

    def test_mesmo_ip_com_porta_diferente_tambem_e_desconhecido(self):
        r, sock, _, logger = criar_r1()
        r.handle_datagram(b"HELLO:10.6.2.1", ("127.0.0.1", 6012))
        self.assertFalse(r.neighbors[R2].active)


class TestVizinhanca(unittest.TestCase):
    def setUp(self):
        self.r, self.sock, self.relogio, self.logger = criar_r1()

    def test_hello_a_cada_5_s_para_todos_os_configurados(self):
        self.r.tick()                                   # partida: 1º HELLO
        self.assertEqual(self.sock.para(R2), [packets.Hello("10.6.1.1")])
        self.assertEqual(self.sock.para(R3), [packets.Hello("10.6.1.1")])
        self.sock.limpar()
        self.relogio.t += 4.5
        self.r.tick()
        self.assertEqual(self.sock.enviados, [])        # ainda não deu 5 s
        self.relogio.t += 0.5
        self.r.tick()
        self.assertEqual(len(self.sock.enviados), 2)    # 5 s: HELLO de novo, mesmo sem vizinho ativo

    def test_primeiro_hello_ativa_e_associa_endereco(self):
        hello(self.r, R2, "10.6.2.1")
        self.assertEqual(self.r.get_active_neighbors(), [("10.6.2.1", "127.0.0.1", 6002)])
        self.assertTrue(self.logger.tem("VIZINHO", "10.6.2.1 (127.0.0.1:6002) ficou ATIVO"))

    def test_ficar_ativo_gera_lsp_imediato_com_seq_unix_time(self):
        antes = int(time.time())
        hello(self.r, R2, "10.6.2.1")
        lsps = [p for p in self.sock.para(R2) if isinstance(p, packets.Lsp)]
        self.assertEqual(lsps[0].origin, "10.6.1.1")
        self.assertEqual(lsps[0].neighbors, {"10.6.2.1": 1})
        self.assertTrue(antes <= lsps[0].seq <= int(time.time()))   # RF10: 1º seq = Unix time
        self.assertEqual(self.sock.para(R3), [])                    # R3 não está ativo

    def test_inativo_apos_20_s_sem_hello_e_novo_lsp(self):
        hello(self.r, R2, "10.6.2.1")
        hello(self.r, R3, "10.6.3.1")
        seq = self.r.seq
        self.relogio.t += 5
        hello(self.r, R3, "10.6.3.1")                   # R3 continua mandando HELLO
        self.relogio.t += 14.5                          # R2: 19,5 s sem HELLO
        self.r.tick()
        self.assertTrue(self.r.neighbors[R2].active)
        self.sock.limpar()
        self.relogio.t += 0.5                           # R2: 20 s sem HELLO
        self.r.tick()
        self.assertFalse(self.r.neighbors[R2].active)
        self.assertTrue(self.logger.tem("VIZINHO", "10.6.2.1 (127.0.0.1:6002) ficou INATIVO"))
        lsps = [p for p in self.sock.para(R3) if isinstance(p, packets.Lsp)]
        self.assertEqual(lsps[-1], packets.Lsp("10.6.1.1", seq + 1, {"10.6.3.1": 7}))   # RF08
        self.assertEqual([p for p in self.sock.para(R2) if isinstance(p, packets.Lsp)], [])

    def test_hello_de_vizinho_ja_ativo_nao_gera_lsp(self):
        hello(self.r, R2, "10.6.2.1")
        seq = self.r.seq
        self.relogio.t += 5
        hello(self.r, R2, "10.6.2.1")
        self.assertEqual(self.r.seq, seq)

    def test_vizinho_volta_depois_de_inativo(self):
        hello(self.r, R2, "10.6.2.1")
        self.relogio.t += 20
        self.r.tick()
        self.assertFalse(self.r.neighbors[R2].active)
        hello(self.r, R2, "10.6.2.1")
        self.assertTrue(self.r.neighbors[R2].active)
        self.assertEqual(self.r.get_lsdb()["10.6.1.1"][1], {"10.6.2.1": 1})


class TestLspProprio(unittest.TestCase):
    def setUp(self):
        self.r, self.sock, self.relogio, self.logger = criar_r1()

    def test_nao_ha_lsp_na_partida(self):
        self.r.tick()
        self.assertIsNone(self.r.seq)                   # D30
        self.assertEqual(self.r.lsdb, {})
        self.assertFalse(any(isinstance(p, packets.Lsp) for p in self.sock.para(R2)))

    def test_renovacao_a_cada_30_s_mesmo_sem_mudanca(self):
        hello(self.r, R2, "10.6.2.1")                   # LSP por mudança em t=1000
        seq = self.r.seq
        for _ in range(5):                              # HELLOs mantêm R2 ativo
            self.relogio.t += 5
            hello(self.r, R2, "10.6.2.1")
            self.r.tick()
        self.assertEqual(self.r.seq, seq)               # t=1025: ainda sem renovação
        self.relogio.t += 5                             # t=1030: 30 s desde a partida
        self.r.tick()
        self.assertEqual(self.r.seq, seq + 1)           # RF09, D32
        self.assertTrue(self.logger.tem("LSP", "renovacao periodica"))

    def test_renovacao_sem_vizinhos_ativos_tem_lista_vazia(self):
        self.relogio.t += 30
        self.r.tick()
        self.assertEqual(self.r.get_lsdb()["10.6.1.1"][1], {})
        self.assertEqual(packets.encode(packets.Lsp("10.6.1.1", self.r.seq, {})),
                         ("LSP:10.6.1.1:%d:" % self.r.seq).encode())   # formato do enunciado


class TestRecebimentoDeLsp(unittest.TestCase):
    def setUp(self):
        self.r, self.sock, self.relogio, self.logger = criar_r1()
        hello(self.r, R2, "10.6.2.1")
        hello(self.r, R3, "10.6.3.1")
        self.sock.limpar()

    def test_regra1_propria_origem_descartada(self):
        seq_proprio = self.r.lsdb["10.6.1.1"].seq
        lsp(self.r, R2, "10.6.1.1", seq_proprio + 100, {"10.6.2.1": 1})
        self.assertEqual(self.r.lsdb["10.6.1.1"].seq, seq_proprio)
        self.assertEqual(self.sock.enviados, [])
        self.assertTrue(self.logger.tem("LSP", "descartado (propria origem)"))

    def test_regra3_novo_e_reenviado_a_todos_exceto_quem_mandou(self):
        lsp(self.r, R2, "10.6.4.1", 500, {"10.6.2.1": 2, "10.6.3.1": 3})
        self.assertEqual(self.r.get_lsdb()["10.6.4.1"], (500, {"10.6.2.1": 2, "10.6.3.1": 3}))
        self.assertEqual(self.sock.enviados, [(b"LSP:10.6.4.1:500:10.6.2.1=2;10.6.3.1=3", R3)])
        self.assertTrue(self.logger.tem("LSP", "LSP novo: 10.6.4.1 seq 500"))

    def test_regra2_copia_e_antigo_descartados(self):
        lsp(self.r, R2, "10.6.4.1", 500, {"10.6.2.1": 2})
        self.sock.limpar()
        lsp(self.r, R3, "10.6.4.1", 500, {"10.6.2.1": 2})   # cópia (seq igual)
        lsp(self.r, R3, "10.6.4.1", 499, {"10.6.3.1": 3})   # antigo (seq menor)
        self.assertEqual(self.sock.enviados, [])
        self.assertEqual(self.r.get_lsdb()["10.6.4.1"], (500, {"10.6.2.1": 2}))
        self.assertTrue(self.logger.tem("LSP", "descartado (copia/antigo): 10.6.4.1 seq 500"))
        self.assertTrue(self.logger.tem("LSP", "descartado (copia/antigo): 10.6.4.1 seq 499"))

    def test_seq_maior_substitui(self):
        lsp(self.r, R2, "10.6.4.1", 500, {"10.6.2.1": 2})
        lsp(self.r, R3, "10.6.4.1", 501, {"10.6.3.1": 3})
        self.assertEqual(self.r.get_lsdb()["10.6.4.1"], (501, {"10.6.3.1": 3}))

    def test_reenvio_sai_no_formato_exato_mesmo_com_sobras_toleradas(self):
        self.r.handle_datagram(b"LSP:10.6.4.1:500:10.6.2.1=2;\n", R2)
        self.assertEqual(self.sock.enviados, [(b"LSP:10.6.4.1:500:10.6.2.1=2", R3)])   # D35

    def test_lsp_de_vizinho_configurado_ainda_inativo_e_aceito(self):
        r, sock, _, _ = criar_r1()                      # ninguém ativo ainda
        lsp(r, R2, "10.6.2.1", 700, {"10.6.1.1": 1})
        self.assertIn("10.6.2.1", r.get_lsdb())          # D05
        self.assertEqual(sock.enviados, [])              # ninguém ativo para reenviar


class TestSincronizacao(unittest.TestCase):
    def test_novo_vizinho_recebe_todos_os_lsps_inclusive_o_proprio(self):
        r, sock, relogio, logger = criar_r1()
        hello(r, R2, "10.6.2.1")
        lsp(r, R2, "10.6.4.1", 500, {"10.6.2.1": 2})
        lsp(r, R2, "10.6.2.1", 600, {"10.6.1.1": 1, "10.6.4.1": 2})
        sock.limpar()
        hello(r, R3, "10.6.3.1")
        origens = [p.origin for p in sock.para(R3) if isinstance(p, packets.Lsp)]
        # 1º o novo LSP próprio; depois a cópia de TODA a LSDB (D31)
        self.assertEqual(origens[0], "10.6.1.1")
        self.assertEqual(sorted(origens[1:]), ["10.6.1.1", "10.6.2.1", "10.6.4.1"])
        self.assertTrue(logger.tem("LSP", "sincronizacao: 3 LSPs enviados a 10.6.3.1"))


class TestEnvelhecimento(unittest.TestCase):
    def test_lsp_alheio_removido_apos_90_s_e_proprio_nunca(self):
        r, sock, relogio, logger = criar_r1()
        hello(r, R2, "10.6.2.1")
        lsp(r, R2, "10.6.2.1", 600, {"10.6.1.1": 1})
        self.assertIn("10.6.2.0/24", r.get_table())
        relogio.t += 89.5
        hello(r, R2, "10.6.2.1")                         # mantém o vizinho ativo
        r.tick()
        self.assertIn("10.6.2.1", r.lsdb)
        relogio.t += 0.5                                  # 90 s sem renovação
        r.tick()
        self.assertNotIn("10.6.2.1", r.lsdb)              # RF14
        self.assertIn("10.6.1.1", r.lsdb)                 # o próprio não envelhece
        self.assertTrue(logger.tem("LSP", "LSP de 10.6.2.1 envelhecido"))
        self.assertTrue(logger.tem("TABELA", "LSP de 10.6.2.1 envelhecido"))

    def test_renovacao_reinicia_a_contagem(self):
        r, sock, relogio, _ = criar_r1()
        lsp(r, R2, "10.6.4.1", 500, {})
        relogio.t += 60
        lsp(r, R2, "10.6.4.1", 501, {})
        relogio.t += 60                                   # 120 s do 1º, 60 s do 2º
        r.tick()
        self.assertIn("10.6.4.1", r.lsdb)


class TestTabela(unittest.TestCase):
    def montar_grupo(self):
        """R1 recebe os LSPs do anel de 4 roteadores dos testes: R1-R2=1, R2-R4=2, R4-R3=3, R3-R1=7."""
        r, sock, relogio, logger = criar_r1()
        hello(r, R2, "10.6.2.1")
        hello(r, R3, "10.6.3.1")
        lsp(r, R2, "10.6.2.1", 600, {"10.6.1.1": 1, "10.6.4.1": 2})
        lsp(r, R2, "10.6.4.1", 601, {"10.6.2.1": 2, "10.6.3.1": 3})
        lsp(r, R3, "10.6.3.1", 602, {"10.6.4.1": 3, "10.6.1.1": 7})
        return r, sock, relogio, logger

    def test_tabela_igual_a_esperada_no_anel(self):
        r, _, _, logger = self.montar_grupo()
        self.assertEqual(r.get_table(), {"10.6.2.0/24": ("10.6.2.1", 1),
                                         "10.6.4.0/24": ("10.6.2.1", 3),
                                         "10.6.3.0/24": ("10.6.2.1", 6)})
        self.assertTrue(logger.tem("TABELA", "MUDOU"))

    def test_route_for_devolve_par_do_proximo_salto(self):
        r, _, _, _ = self.montar_grupo()
        self.assertEqual(r.route_for("10.6.3.1"), ("10.6.2.1", R2))
        self.assertEqual(r.route_for("10.6.3.50"), ("10.6.2.1", R2))   # qualquer host da /24
        self.assertIsNone(r.route_for("10.6.99.1"))

    def test_queda_de_r2_usa_caminho_alternativo(self):
        r, sock, relogio, _ = self.montar_grupo()
        relogio.t += 5
        hello(r, R3, "10.6.3.1")
        relogio.t += 15                                   # R2: 20 s sem HELLO
        r.tick()
        # Momento 1: só R1 percebeu a queda. O LSP de R4 ainda lista R2 (R4 não detectou ainda),
        # então pelo grafo dirigido (D07) ainda existe R1->R3->R4->R2. Estado transitório normal.
        self.assertEqual(r.get_table(), {"10.6.3.0/24": ("10.6.3.1", 7),
                                         "10.6.4.0/24": ("10.6.3.1", 10),
                                         "10.6.2.0/24": ("10.6.3.1", 12)})
        # Momento 2: R4 também detecta a queda e inunda um LSP sem R2 (chega a R1 via R3)
        lsp(r, R3, "10.6.4.1", 602, {"10.6.3.1": 3})
        self.assertEqual(r.get_table(), {"10.6.3.0/24": ("10.6.3.1", 7),
                                         "10.6.4.0/24": ("10.6.3.1", 10)})
        self.assertEqual(r.route_for("10.6.4.1"), ("10.6.3.1", R3))

    def test_lsp_antes_do_proprio_nao_quebra(self):
        r, _, _, _ = criar_r1()
        lsp(r, R2, "10.6.2.1", 600, {"10.6.1.1": 1})     # ainda não há LSP próprio
        self.assertEqual(r.get_table(), {})

    def test_recalculo_sem_mudanca_registra_uma_linha(self):
        r, _, relogio, logger = self.montar_grupo()
        lsp(r, R2, "10.6.4.1", 610, {"10.6.2.1": 2, "10.6.3.1": 3})   # mesmo conteúdo, seq novo
        self.assertTrue(logger.tem("TABELA", "LSP novo de 10.6.4.1): sem mudanca"))

    def test_is_local(self):
        r, _, _, _ = criar_r1()
        self.assertTrue(r.is_local("10.6.1.1"))
        self.assertTrue(r.is_local("10.6.1.50"))
        self.assertFalse(r.is_local("10.6.2.1"))


class TestRobustez(unittest.TestCase):
    def test_malformado_e_descartado(self):
        r, sock, _, logger = criar_r1()
        for lixo in [b"OLA:10.6.2.1", b"HELLO", b"LSP:10.6.2.1:abc:", b"\xff\xfe"]:
            r.handle_datagram(lixo, R2)
        self.assertEqual(sock.enviados, [])
        self.assertTrue(logger.tem("DESCARTE", "malformado"))

    def test_dados_e_icmp_vao_para_o_forwarder(self):
        r, _, _, _ = criar_r1()
        r.handle_datagram(b"DADOS:10.6.3.1:10.6.1.1:16:0:oi", R2)
        r.handle_datagram(b"ICMP:10.6.3.1:10.6.1.1:16:7:8", R2)
        tipos = [type(p).__name__ for p, _ in r.forwarder.recebidos]
        self.assertEqual(tipos, ["Dados", "Icmp"])

    def test_erro_num_pacote_nao_mata_a_thread_de_recepcao(self):
        r, _, _, logger = criar_r1()

        class Parar(BaseException):
            pass

        class SocketComFila:
            def __init__(self, fila):
                self.fila = fila

            def recvfrom(self, tamanho):
                if not self.fila:
                    raise Parar()
                return self.fila.pop(0)

            def sendto(self, data, peer):
                pass

        class ForwarderQuebrado:
            def handle(self, pkt, peer):
                raise RuntimeError("falha simulada")

        r.sock = SocketComFila([(b"DADOS:10.6.3.1:10.6.1.1:16:0:oi", R2), (b"HELLO:10.6.2.1", R2)])
        r.forwarder = ForwarderQuebrado()
        with self.assertRaises(Parar):
            r.receive_loop()
        self.assertTrue(logger.tem("ERRO", "falha simulada"))
        self.assertTrue(r.neighbors[R2].active)          # o HELLO seguinte foi processado (D33)


class TestConstantes(unittest.TestCase):
    def test_tick_menor_que_os_temporizadores(self):
        self.assertLess(router.TICK, router.HELLO_INTERVAL)


if __name__ == "__main__":
    unittest.main()
