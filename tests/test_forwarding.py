"""Testes do forwarding.py (plano §4.5), sem rede: Router falso e relógio real.

Dono: Frederico. Rodar da raiz do repositório:

    python3 -m unittest tests.test_forwarding -v

O roteador falso é o R2 (10.6.2.1) do triângulo da apresentação: vizinhos R1 e R3, e guarda
tudo o que o Forwarder manda enviar, para os testes conferirem pacote a pacote.
"""

import contextlib
import io
import threading
import unittest
from unittest import mock

import forwarding
import packets
from forwarding import Forwarder

EU = "10.6.2.1"
R1, R3 = "10.6.1.1", "10.6.3.1"
PEER1 = ("127.0.0.1", 6001)
PEER3 = ("127.0.0.1", 6003)


class LoggerFalso:
    def __init__(self):
        self.linhas = []   # [(categoria, texto)]

    def log(self, categoria, texto, terminal=True):
        self.linhas.append((categoria, texto))


class RoteadorFalso:
    """Tem só o que o Forwarder usa do Router: address, lock, logger, route_for, is_local, send."""

    def __init__(self, address):
        self.address = address
        self.lock = threading.RLock()
        self.logger = LoggerFalso()
        self.rotas = {}          # {'10.6.3.0/24': ('10.6.3.1', ('127.0.0.1', 6003))}
        self.enviados = []       # [(bytes, peer)]
        self.ao_enviar = None    # função opcional chamada a cada envio (para simular respostas)

    def route_for(self, dst):
        return self.rotas.get(packets.network_of(dst))

    def is_local(self, addr):
        return packets.same_network(addr, self.address)

    def send(self, data, peer):
        self.enviados.append((data, peer))
        if self.ao_enviar is not None:
            self.ao_enviar(data, peer)


class Base(unittest.TestCase):
    def setUp(self):
        self.router = RoteadorFalso(EU)
        self.router.rotas = {"10.6.1.0/24": (R1, PEER1), "10.6.3.0/24": (R3, PEER3)}
        self.fw = Forwarder(self.router)

    def capturar(self, funcao, *args):
        """Chama a função guardando o que ela imprime. Devolve (retorno, texto impresso)."""
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            retorno = funcao(*args)
        return retorno, saida.getvalue()

    def tratar(self, pkt, peer=PEER1):
        return self.capturar(self.fw.handle, pkt, peer)[1]

    def enviados(self):
        """Pacotes enviados, já decodificados: [(pacote, peer)]."""
        return [(packets.parse(dados), peer) for dados, peer in self.router.enviados]

    def log(self, categoria):
        return " | ".join(t for c, t in self.router.logger.linhas if c == categoria)

    def responder(self, tipo, origem):
        """Faz o roteador falso devolver, assim que o pedido de ping sair, uma resposta ICMP."""
        def ao_enviar(dados, peer):
            pedido = packets.parse(dados)
            self.fw.handle(packets.Icmp(origem, EU, 16, pedido.id, tipo), peer)
        self.router.ao_enviar = ao_enviar


class TestOriginar(Base):
    def test_msg_sem_rota_nao_envia(self):
        texto = self.fw.send_data("10.6.9.1", "oi")
        self.assertEqual(texto, "Destino inalcancavel: sem rota para 10.6.9.0/24 (nada foi enviado)")
        self.assertEqual(self.router.enviados, [])

    def test_msg_com_rota_envia_ao_proximo_salto(self):
        texto = self.fw.send_data("10.6.3.1", "Oi pessoal!")
        self.assertEqual(texto, "DADOS enviado para 10.6.3.1 via 10.6.3.1")
        self.assertEqual(self.enviados(),
                         [(packets.Dados(EU, "10.6.3.1", 16, 0, "Oi pessoal!"), PEER3)])
        self.assertIn("TTL 16", self.log("ENCAMINHA"))

    def test_msg_para_a_propria_rede_e_entregue_localmente(self):
        texto, saida = self.capturar(self.fw.send_data, "10.6.2.50", "alo")
        self.assertIn("entregue ao proprio roteador", texto)
        self.assertIn("Mensagem de 10.6.2.1 para 10.6.2.50: alo", saida)
        self.assertEqual(self.router.enviados, [])

    def test_ping_sem_rota_nao_envia_e_nao_deixa_pendente(self):
        texto = self.fw.ping("10.6.9.1")
        self.assertTrue(texto.startswith("Destino inalcancavel: sem rota para 10.6.9.0/24"))
        self.assertEqual(self.router.enviados, [])
        self.assertEqual(self.fw.pending, {})

    def test_ping_envia_pedido_com_o_ttl_pedido_e_id_do_contador(self):
        self.responder(packets.ICMP_ECHO_REPLY, R3)
        self.fw.ping(R3, 3)
        self.fw.ping(R3)
        enviados = [p for p, _ in self.enviados()]
        self.assertEqual(enviados, [packets.Icmp(EU, R3, 3, 1, 8), packets.Icmp(EU, R3, 16, 2, 8)])
        self.assertEqual(self.router.enviados[0][1], PEER3)
        self.assertIn("pedido de eco", self.log("ICMP"))

    def test_ping_resposta_de_eco(self):
        self.responder(packets.ICMP_ECHO_REPLY, R3)
        self.assertRegex(self.fw.ping(R3), r"^Resposta de eco de 10\.6\.3\.1 \(id=1\) RTT=\d+\.\d\d ms$")
        self.assertEqual(self.fw.pending, {})

    def test_ping_tempo_excedido(self):
        self.responder(packets.ICMP_TIME_EXCEEDED, R1)
        self.assertRegex(self.fw.ping(R3, 1), r"^Tempo excedido informado por 10\.6\.1\.1 \(id=1\) RTT=")

    def test_ping_destino_inalcancavel(self):
        self.responder(packets.ICMP_DEST_UNREACHABLE, R1)
        self.assertRegex(self.fw.ping(R3), r"^Destino inalcancavel informado por 10\.6\.1\.1 \(id=1\) RTT=")

    def test_ping_resposta_que_chega_em_outra_thread(self):
        def depois(dados, peer):
            pedido = packets.parse(dados)
            resposta = packets.Icmp(R3, EU, 16, pedido.id, packets.ICMP_ECHO_REPLY)
            threading.Timer(0.05, self.fw.handle, (resposta, PEER3)).start()
        self.router.ao_enviar = depois
        self.assertTrue(self.fw.ping(R3).startswith("Resposta de eco de 10.6.3.1"))

    def test_ping_timeout(self):
        with mock.patch.object(forwarding, "PING_TIMEOUT", 0.05):
            texto = self.fw.ping(R3)
        self.assertTrue(texto.startswith("Timeout: nenhuma resposta em"))
        self.assertIn("(id=1)", texto)
        self.assertEqual(self.fw.pending, {})

    def test_resposta_com_id_de_outro_ping_nao_acorda_este(self):
        def errada(dados, peer):
            self.fw.handle(packets.Icmp(R3, EU, 16, 99, packets.ICMP_ECHO_REPLY), peer)
        self.router.ao_enviar = errada
        with mock.patch.object(forwarding, "PING_TIMEOUT", 0.05):
            texto, saida = self.capturar(self.fw.ping, R3)
        self.assertTrue(texto.startswith("Timeout"))
        self.assertIn("Resposta de eco de 10.6.3.1 (id=99)", saida)   # resposta atrasada e exibida (D18)

    def test_ping_ao_proprio_endereco_responde_sem_ir_a_rede(self):
        texto = self.fw.ping("10.6.2.50")
        self.assertRegex(texto, r"^Resposta de eco de 10\.6\.2\.50 \(id=1\) RTT=")
        self.assertEqual(self.router.enviados, [])


class TestReceberLocal(Base):
    def test_dados_mostra_origem_destino_e_mensagem(self):
        saida = self.tratar(packets.Dados(R1, EU, 16, 0, "Oi pessoal!"))
        self.assertIn("Mensagem de 10.6.1.1 para 10.6.2.1: Oi pessoal!", saida)

    def test_dados_para_outro_host_da_rede(self):
        saida = self.tratar(packets.Dados(R1, "10.6.2.50", 16, 0, "oi"))
        self.assertIn("Mensagem de 10.6.1.1 para 10.6.2.50: oi", saida)
        self.assertEqual(self.router.enviados, [])

    def test_eco_responde_com_tipo_0_mesmo_id_e_origem_do_destino_do_pedido(self):
        self.tratar(packets.Icmp(R1, "10.6.2.50", 7, 42, packets.ICMP_ECHO_REQUEST))
        self.assertEqual(self.enviados(), [(packets.Icmp("10.6.2.50", R1, 16, 42, 0), PEER1)])
        self.assertIn("tipo 0", self.log("ICMP"))

    def test_eco_sem_rota_de_volta_nao_envia(self):
        self.tratar(packets.Icmp("10.6.9.1", EU, 16, 5, packets.ICMP_ECHO_REQUEST))
        self.assertEqual(self.router.enviados, [])
        self.assertIn("sem rota de volta", self.log("DESCARTE"))

    def test_resposta_icmp_sem_ping_pendente_e_exibida(self):
        for tipo, inicio in [(0, "Resposta de eco de"), (11, "Tempo excedido informado por"),
                             (3, "Destino inalcancavel informado por")]:
            saida = self.tratar(packets.Icmp(R3, EU, 16, 77, tipo))
            self.assertTrue(saida.startswith(inicio + " 10.6.3.1 (id=77)"), saida)
        self.assertEqual(self.router.enviados, [])


class TestTransito(Base):
    def test_encaminha_com_ttl_decrementado(self):
        self.tratar(packets.Dados(R1, R3, 5, 0, "oi"))
        self.assertEqual(self.enviados(), [(packets.Dados(R1, R3, 4, 0, "oi"), PEER3)])
        log = self.log("ENCAMINHA")
        self.assertIn("10.6.3.1", log)
        self.assertIn("TTL 4", log)

    def test_encaminha_icmp_de_eco_e_de_erro_com_ttl_decrementado(self):
        self.tratar(packets.Icmp(R1, R3, 9, 3, packets.ICMP_ECHO_REQUEST))
        self.tratar(packets.Icmp(R3, "10.6.1.9", 9, 3, packets.ICMP_TIME_EXCEEDED))
        self.assertEqual(self.enviados(), [(packets.Icmp(R1, R3, 8, 3, 8), PEER3),
                                           (packets.Icmp(R3, "10.6.1.9", 8, 3, 11), PEER1)])

    def test_ttl_1_gera_tempo_excedido_para_a_origem(self):
        self.tratar(packets.Icmp(R1, R3, 1, 42, packets.ICMP_ECHO_REQUEST))
        # origem = este roteador, TTL 16, id copiado; o pacote original NAO e encaminhado
        self.assertEqual(self.enviados(), [(packets.Icmp(EU, R1, 16, 42, 11), PEER1)])
        self.assertIn("tipo 11", self.log("ICMP"))

    def test_ttl_0_na_chegada_tambem_gera_tempo_excedido(self):
        self.tratar(packets.Dados(R1, R3, 0, 0, "oi"))
        self.assertEqual(self.enviados(), [(packets.Icmp(EU, R1, 16, 0, 11), PEER1)])

    def test_ttl_e_checado_antes_da_rota(self):
        # TTL 1 E sem rota: o enunciado manda decrementar primeiro -> tipo 11, nao 3
        self.tratar(packets.Dados(R1, "10.6.9.1", 1, 0, "oi"))
        self.assertEqual(self.enviados(), [(packets.Icmp(EU, R1, 16, 0, 11), PEER1)])

    def test_sem_rota_gera_destino_inalcancavel_para_a_origem(self):
        self.tratar(packets.Dados(R1, "10.6.9.1", 5, 0, "oi"))
        self.assertEqual(self.enviados(), [(packets.Icmp(EU, R1, 16, 0, 3), PEER1)])
        self.assertIn("tipo 3", self.log("ICMP"))

    def test_eco_0_e_eco_8_em_transito_geram_erro(self):
        # D10: so ICMP 11 e 3 sao "erros"; 0 e 8 geram erro normalmente
        self.tratar(packets.Icmp(R1, R3, 1, 1, packets.ICMP_ECHO_REQUEST))
        self.tratar(packets.Icmp(R1, R3, 1, 2, packets.ICMP_ECHO_REPLY))
        self.assertEqual([p for p, _ in self.enviados()],
                         [packets.Icmp(EU, R1, 16, 1, 11), packets.Icmp(EU, R1, 16, 2, 11)])

    def test_nunca_gera_erro_em_resposta_a_erro(self):
        self.tratar(packets.Icmp(R1, R3, 1, 1, packets.ICMP_TIME_EXCEEDED))        # TTL chega a 0
        self.tratar(packets.Icmp(R1, "10.6.9.1", 5, 2, packets.ICMP_DEST_UNREACHABLE))  # sem rota
        self.assertEqual(self.router.enviados, [])
        self.assertIn("ja era um erro", self.log("DESCARTE"))

    def test_erro_sem_rota_de_volta_nao_e_enviado(self):
        self.tratar(packets.Dados("10.6.9.1", R3, 1, 0, "oi"))
        self.assertEqual(self.router.enviados, [])
        self.assertIn("sem rota de volta", self.log("DESCARTE"))


if __name__ == "__main__":
    unittest.main()