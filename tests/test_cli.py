"""Testes do cli.py (dono: William), com um roteador e um forwarder falsos."""

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

import cli


class RouterFalso:
    address = "10.6.1.1"

    def __init__(self, tabela=None, lsdb=None, vizinhos=None):
        self.tabela = tabela or {}
        self.lsdb = lsdb or {}
        self.vizinhos = vizinhos or []

    def get_table(self):
        return self.tabela

    def get_lsdb(self):
        return self.lsdb

    def get_active_neighbors(self):
        return self.vizinhos


class ForwarderFalso:
    def __init__(self):
        self.chamadas = []

    def send_data(self, dst, text):
        self.chamadas.append(("msg", dst, text))
        return "DADOS enviado para %s" % dst

    def ping(self, dst, ttl):
        self.chamadas.append(("ping", dst, ttl))
        return "resposta de %s" % dst


# Estado de R1 num anel de 4 roteadores (R1-R2=1, R2-R4=2, R4-R3=3, R3-R1=7), só para os testes
TABELA_R1 = {"10.6.3.0/24": ("10.6.2.1", 6), "10.6.2.0/24": ("10.6.2.1", 1),
             "10.6.4.0/24": ("10.6.2.1", 3)}
LSDB_R1 = {"10.6.2.1": (1795111003, {"10.6.4.1": 2, "10.6.1.1": 1}),
           "10.6.1.1": (1795111000, {"10.6.3.1": 7, "10.6.2.1": 1}),
           "10.6.3.1": (1795111001, {})}
VIZINHOS_R1 = [("10.6.3.1", "192.168.0.13", 6000), ("10.6.2.1", "192.168.0.12", 6000)]


class TestConsultas(unittest.TestCase):
    def setUp(self):
        self.router = RouterFalso(TABELA_R1, LSDB_R1, VIZINHOS_R1)
        self.fwd = ForwarderFalso()

    def rodar(self, linha):
        return cli.executar(linha, self.router, self.fwd)

    def test_tabela_ordenada_com_colunas_do_enunciado(self):
        texto, continuar = self.rodar("tabela")
        linhas = texto.splitlines()
        self.assertTrue(continuar)
        self.assertEqual(linhas[0].split(), ["Rede", "destino", "Proximo", "salto", "Custo"])
        self.assertEqual(linhas[1].split(), ["10.6.2.0/24", "10.6.2.1", "1"])
        self.assertEqual(linhas[2].split(), ["10.6.3.0/24", "10.6.2.1", "6"])
        self.assertEqual(linhas[3].split(), ["10.6.4.0/24", "10.6.2.1", "3"])

    def test_lsdb_mostra_origem_seq_vizinhos_e_custos(self):
        texto, _ = self.rodar("lsdb")
        linhas = texto.splitlines()
        self.assertIn("Origem", linhas[0])
        self.assertEqual(linhas[1].split(), ["10.6.1.1", "1795111000", "10.6.2.1=1,", "10.6.3.1=7"])
        self.assertEqual(linhas[2].split(), ["10.6.2.1", "1795111003", "10.6.1.1=1,", "10.6.4.1=2"])
        self.assertEqual(linhas[3].split(), ["10.6.3.1", "1795111001", "(nenhum)"])

    def test_vizinhos_ativos(self):
        texto, _ = self.rodar("vizinhos")
        linhas = texto.splitlines()
        self.assertEqual(linhas[1].split(), ["10.6.2.1", "192.168.0.12", "6000"])
        self.assertEqual(linhas[2].split(), ["10.6.3.1", "192.168.0.13", "6000"])

    def test_ordem_numerica_dos_enderecos(self):
        router = RouterFalso(tabela={"10.6.10.0/24": ("10.6.2.1", 9), "10.6.2.0/24": ("10.6.2.1", 1)})
        texto, _ = cli.executar("tabela", router, self.fwd)
        self.assertIn("10.6.2.0/24", texto.splitlines()[1])   # 2 antes de 10

    def test_estruturas_vazias(self):
        vazio = RouterFalso()
        self.assertIn("vazia", cli.executar("tabela", vazio, self.fwd)[0])
        self.assertIn("vazia", cli.executar("lsdb", vazio, self.fwd)[0])
        self.assertIn("Nenhum vizinho ativo", cli.executar("vizinhos", vazio, self.fwd)[0])


class TestComandosGerais(unittest.TestCase):
    def setUp(self):
        self.fwd = ForwarderFalso()

    def rodar(self, linha):
        return cli.executar(linha, RouterFalso(), self.fwd)

    def test_linha_vazia_nao_faz_nada(self):
        self.assertEqual(self.rodar("   "), ("", True))

    def test_sair(self):
        texto, continuar = self.rodar("sair")
        self.assertFalse(continuar)

    def test_comando_desconhecido_mostra_os_comandos(self):
        texto, continuar = self.rodar("ajuda")
        self.assertTrue(continuar)
        self.assertIn("Comando desconhecido", texto)
        for comando in ["tabela", "lsdb", "vizinhos", "msg", "ping", "sair"]:
            self.assertIn(comando, texto)

    def test_uso_errado_nao_envia_nada(self):
        self.assertIn("Uso: msg", self.rodar("msg")[0])
        self.assertIn("Uso: msg", self.rodar("msg 10.6.2.1")[0])
        self.assertIn("Uso: ping", self.rodar("ping")[0])
        self.assertIn("Uso: ping", self.rodar("ping 10.6.2.1 3 4")[0])
        self.assertEqual(self.fwd.chamadas, [])


class TestMsgEPing(unittest.TestCase):
    def setUp(self):
        self.fwd = ForwarderFalso()

    def rodar(self, linha):
        return cli.executar(linha, RouterFalso(), self.fwd)

    def test_msg_envia_resto_da_linha_com_espacos(self):
        texto, _ = self.rodar("msg 10.6.3.1 Oi pessoal, tudo bem?")
        self.assertEqual(self.fwd.chamadas, [("msg", "10.6.3.1", "Oi pessoal, tudo bem?")])
        self.assertEqual(texto, "DADOS enviado para 10.6.3.1")

    def test_msg_recusa_dois_pontos_acento_e_destino_invalido(self):
        self.assertIn("Texto invalido", self.rodar("msg 10.6.3.1 hora: 10h")[0])
        self.assertIn("Texto invalido", self.rodar("msg 10.6.3.1 olá")[0])
        self.assertIn("Destino invalido", self.rodar("msg roteador3 oi")[0])
        self.assertEqual(self.fwd.chamadas, [])

    def test_ping_ttl_padrao_16_e_ttl_informado(self):
        self.rodar("ping 10.6.3.1")
        self.rodar("ping 10.6.3.1 2")
        self.assertEqual(self.fwd.chamadas, [("ping", "10.6.3.1", 16), ("ping", "10.6.3.1", 2)])

    def test_ping_recusa_ttl_invalido(self):
        for ttl in ["0", "-1", "abc", "²", "1.5"]:
            self.assertIn("TTL invalido", self.rodar("ping 10.6.3.1 " + ttl)[0], ttl)
        self.assertIn("Destino invalido", self.rodar("ping 10.6.999.1")[0])
        self.assertEqual(self.fwd.chamadas, [])


class TestSaidaAscii(unittest.TestCase):
    """D39: tudo o que a CLI mostra é ASCII, para não travar em terminal sem suporte a acento."""

    def test_todas_as_saidas_sao_ascii(self):
        router, vazio, fwd = RouterFalso(TABELA_R1, LSDB_R1, VIZINHOS_R1), RouterFalso(), ForwarderFalso()
        textos = [cli.AJUDA]
        for linha in ["tabela", "lsdb", "vizinhos", "sair", "xyz", "msg", "ping"]:
            textos.append(cli.executar(linha, router, fwd)[0])
            textos.append(cli.executar(linha, vazio, fwd)[0])
        for linha in ["msg 10.6.3.1 olá", "msg x oi", "ping x", "ping 10.6.3.1 0"]:
            textos.append(cli.executar(linha, router, fwd)[0])
        for texto in textos:
            texto.encode("ascii")   # levanta UnicodeEncodeError se houver acento


class TestLaco(unittest.TestCase):
    def rodar_laco(self, entradas, router=None, fwd=None):
        saida = io.StringIO()
        with mock.patch("builtins.input", side_effect=entradas), redirect_stdout(saida):
            cli.run(router or RouterFalso(TABELA_R1), fwd or ForwarderFalso())
        return saida.getvalue()

    def test_ctrl_c_durante_o_ping_encerra_sem_erro(self):
        class ForwarderInterrompido(ForwarderFalso):
            def ping(self, dst, ttl):
                raise KeyboardInterrupt
        saida = self.rodar_laco(["ping 10.6.3.1", "tabela"], fwd=ForwarderInterrompido())
        self.assertNotIn("Erro", saida)
        self.assertNotIn("Rede destino", saida)   # encerrou: não executou o comando seguinte

    def test_executa_ate_sair(self):
        saida = self.rodar_laco(["tabela", "sair", "tabela"])
        self.assertEqual(saida.count("Rede destino"), 1)   # o 'tabela' depois de 'sair' não roda
        self.assertIn("Encerrando", saida)

    def test_fim_da_entrada_encerra(self):
        saida = self.rodar_laco(["tabela", EOFError()])
        self.assertIn("Rede destino", saida)

    def test_erro_num_comando_nao_derruba(self):
        class RouterQuebrado(RouterFalso):
            def get_table(self):
                raise RuntimeError("falha simulada")

        saida = self.rodar_laco(["tabela", "vizinhos", "sair"], router=RouterQuebrado())
        self.assertIn("Erro ao executar o comando: falha simulada", saida)
        self.assertIn("Nenhum vizinho ativo", saida)   # o comando seguinte ainda roda


if __name__ == "__main__":
    unittest.main()
