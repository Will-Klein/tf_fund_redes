"""Testes da fase F0: interfaces combinadas, constantes do enunciado e coerência das configs.

Rodar da raiz do repositório:  python3 -m unittest discover tests
"""

import glob
import os
import unittest

import cli
import config
import dijkstra
import forwarding
import log
import packets
import router

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestInterfaces(unittest.TestCase):
    """Os nomes do docs/IMPLEMENTATION_PLAN.md §4 existem (cada dono implementa sem mudar a interface)."""

    def test_packets(self):
        self.assertEqual(packets.Hello._fields, ("addr",))
        self.assertEqual(packets.Lsp._fields, ("origin", "seq", "neighbors"))
        self.assertEqual(packets.Dados._fields, ("src", "dst", "ttl", "id", "msg"))
        self.assertEqual(packets.Icmp._fields, ("src", "dst", "ttl", "id", "type"))
        self.assertTrue(issubclass(packets.MalformedPacket, Exception))
        for nome in ["parse", "encode", "is_virtual_addr", "network_of", "same_network", "valid_text"]:
            self.assertTrue(callable(getattr(packets, nome)), nome)

    def test_config(self):
        self.assertEqual(config.NeighborConf._fields, ("ip", "port", "cost"))
        self.assertEqual(config.Config._fields, ("address", "port", "neighbors"))
        self.assertTrue(issubclass(config.ConfigError, Exception))
        self.assertTrue(callable(config.load_config))

    def test_outros_modulos(self):
        self.assertTrue(callable(dijkstra.dijkstra))
        self.assertTrue(callable(cli.run))
        for nome in ["send_data", "ping", "handle"]:
            self.assertTrue(callable(getattr(forwarding.Forwarder, nome)), nome)
        self.assertTrue(callable(log.Logger.log))
        for nome in ["start", "handle_datagram", "tick", "route_for", "is_local", "send",
                     "get_table", "get_lsdb", "get_active_neighbors"]:
            self.assertTrue(callable(getattr(router.Router, nome)), nome)


class TestConstantesDoEnunciado(unittest.TestCase):
    """Números que o enunciado fixa."""

    def test_temporizadores(self):
        self.assertEqual(router.HELLO_INTERVAL, 5)
        self.assertEqual(router.NEIGHBOR_TIMEOUT, 20)
        self.assertEqual(router.LSP_REFRESH, 30)
        self.assertEqual(router.LSP_MAX_AGE, 90)

    def test_ttl_ping_porta(self):
        self.assertEqual(forwarding.TTL_INICIAL, 16)
        self.assertEqual(forwarding.PING_TIMEOUT, 2.0)
        self.assertEqual(config.DEFAULT_PORT, 6000)

    def test_tipos_icmp(self):
        self.assertEqual(packets.ICMP_ECHO_REPLY, 0)
        self.assertEqual(packets.ICMP_DEST_UNREACHABLE, 3)
        self.assertEqual(packets.ICMP_ECHO_REQUEST, 8)
        self.assertEqual(packets.ICMP_TIME_EXCEEDED, 11)


def ler_config_simples(caminho):
    """Leitura mínima só para este teste (a leitura de verdade é config.load_config)."""
    endereco, porta, vizinhos = None, None, []
    with open(caminho) as arquivo:
        linhas = arquivo.readlines()
    for linha in linhas:
        partes = linha.split("#")[0].split()
        if not partes:
            continue
        if partes[0] == "endereco":
            endereco = partes[1]
        elif partes[0] == "porta":
            porta = int(partes[1])
        elif partes[0] == "vizinho":
            vizinhos.append((partes[1], int(partes[2]), int(partes[3])))
    return endereco, porta, vizinhos


class TestConfigsDasTopologias(unittest.TestCase):
    """Enunciado: um enlace existe quando os dois lados listam um ao outro, com o MESMO custo."""

    def verificar_simetria(self, pasta, identificar):
        arquivos = sorted(glob.glob(os.path.join(RAIZ, "configs", pasta, "r*.conf")))
        self.assertTrue(arquivos, "nenhuma config em configs/" + pasta)
        enlaces = {}  # (roteador, vizinho) -> custo
        for caminho in arquivos:
            endereco, porta, vizinhos = ler_config_simples(caminho)
            for ip, porta_viz, custo in vizinhos:
                self.assertGreater(custo, 0)
                enlaces[(endereco, identificar(ip, porta_viz))] = custo
        for (a, b), custo in enlaces.items():
            self.assertEqual(enlaces.get((b, a)), custo, "enlace %s-%s não é simétrico" % (a, b))
        custos = [c for (a, b), c in enlaces.items() if a < b]
        self.assertEqual(len(custos), len(set(custos)), "custos repetidos (D36)")

    def test_local5(self):
        # na mesma máquina, a porta identifica o roteador: 600R -> 10.6.R.1
        self.verificar_simetria("local5", lambda ip, porta: "10.6.%d.1" % (porta - 6000))

    def test_grupo(self):
        # IPs ainda são marcadores IP_Rn -> 10.6.n.1
        self.verificar_simetria("grupo", lambda ip, porta: "10.6.%s.1" % ip.replace("IP_R", ""))

    def test_teste_vdi(self):
        # teste rápido da VDI: só R1 e R3, mesmos marcadores IP_Rn da rede do grupo
        self.verificar_simetria("teste_vdi", lambda ip, porta: "10.6.%s.1" % ip.replace("IP_R", ""))


if __name__ == "__main__":
    unittest.main()
