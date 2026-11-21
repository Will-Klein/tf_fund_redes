"""Testes do packets.py (dono: William): formato exato e leitura estrita dos pacotes."""

import unittest

from packets import (Dados, Hello, Icmp, Lsp, MalformedPacket, encode, is_virtual_addr,
                     network_of, parse, same_network, valid_text)


class TestExemplosDoEnunciado(unittest.TestCase):
    """Os exemplos literais do enunciado: ler e escrever de volta dá exatamente o mesmo texto."""

    EXEMPLOS = [
        (b"HELLO:10.3.1.1", Hello("10.3.1.1")),
        (b"LSP:10.3.1.1:1767712000:10.3.2.1=1;10.3.4.1=3",
         Lsp("10.3.1.1", 1767712000, {"10.3.2.1": 1, "10.3.4.1": 3})),
        (b"LSP:10.3.1.1:1767712001:", Lsp("10.3.1.1", 1767712001, {})),   # lista vazia (RF11)
        (b"DADOS:10.3.1.1:10.3.4.1:16:0:Oi pessoal!", Dados("10.3.1.1", "10.3.4.1", 16, 0, "Oi pessoal!")),
        (b"ICMP:10.3.1.1:10.3.4.1:16:42:8", Icmp("10.3.1.1", "10.3.4.1", 16, 42, 8)),
    ]

    def test_parse(self):
        for dados, pacote in self.EXEMPLOS:
            self.assertEqual(parse(dados), pacote, dados)

    def test_encode(self):
        for dados, pacote in self.EXEMPLOS:
            self.assertEqual(encode(pacote), dados, dados)

    def test_numeros_viram_int(self):
        p = parse(b"ICMP:10.3.1.1:10.3.4.1:16:42:8")
        self.assertEqual((type(p.ttl), type(p.id), type(p.type)), (int, int, int))
        self.assertIsInstance(parse(b"LSP:10.3.1.1:1767712000:10.3.2.1=1").neighbors["10.3.2.1"], int)

    def test_todos_os_tipos_icmp(self):
        for tipo in (0, 3, 8, 11):
            texto = ("ICMP:10.6.1.1:10.6.3.1:16:7:%d" % tipo).encode()
            self.assertEqual(parse(texto).type, tipo)
            self.assertEqual(encode(parse(texto)), texto)


class TestTolerancias(unittest.TestCase):
    """D12: aceita '\\n'/'\\r\\n' no fim e itens vazios na lista do LSP; encode nunca gera sobras."""

    def test_quebra_de_linha_no_fim(self):
        self.assertEqual(parse(b"HELLO:10.3.1.1\n"), Hello("10.3.1.1"))
        self.assertEqual(parse(b"HELLO:10.3.1.1\r\n"), Hello("10.3.1.1"))
        self.assertEqual(parse(b"DADOS:10.3.1.1:10.3.4.1:16:0:oi\n").msg, "oi")

    def test_ponto_e_virgula_no_fim(self):
        p = parse(b"LSP:10.3.1.1:5:10.3.2.1=1;10.3.4.1=3;")
        self.assertEqual(p.neighbors, {"10.3.2.1": 1, "10.3.4.1": 3})
        self.assertEqual(encode(p), b"LSP:10.3.1.1:5:10.3.2.1=1;10.3.4.1=3")   # D35: sai sem sobras

    def test_mensagem_mantem_espacos(self):
        self.assertEqual(parse(b"DADOS:10.3.1.1:10.3.4.1:16:0:  a  b ").msg, "  a  b ")


class TestMalformados(unittest.TestCase):
    """Enunciado: malformado = tipo desconhecido, número errado de campos, valores não numéricos;
    D12/D13 completam com endereço inválido, custo <= 0, tipo ICMP desconhecido e fora do ASCII."""

    def malformado(self, dados):
        with self.assertRaises(MalformedPacket, msg=dados):
            parse(dados)

    def test_tipo_desconhecido(self):
        for dados in [b"OLA:10.3.1.1", b"hello:10.3.1.1", b"", b"\n", b"HELLO"]:
            self.malformado(dados)

    def test_numero_errado_de_campos(self):
        for dados in [b"HELLO:10.3.1.1:extra", b"LSP:10.3.1.1:5", b"LSP:10.3.1.1:5:10.3.2.1=1:x",
                      b"DADOS:10.3.1.1:10.3.4.1:16:0", b"ICMP:10.3.1.1:10.3.4.1:16:42",
                      b"ICMP:10.3.1.1:10.3.4.1:16:42:8:9"]:
            self.malformado(dados)

    def test_mensagem_com_dois_pontos(self):
        self.malformado(b"DADOS:10.3.1.1:10.3.4.1:16:0:hora: 10h")   # vira campo a mais (D13)

    def test_valores_nao_numericos(self):
        for dados in [b"LSP:10.3.1.1:abc:10.3.2.1=1",          # seq
                      b"LSP:10.3.1.1:5:10.3.2.1=x",            # custo
                      b"DADOS:10.3.1.1:10.3.4.1:dez:0:oi",     # TTL
                      b"DADOS:10.3.1.1:10.3.4.1:16::oi",       # id vazio
                      b"ICMP:10.3.1.1:10.3.4.1:16:42:oito",    # tipo
                      b"ICMP:10.3.1.1:10.3.4.1:-1:42:8",       # sinal não é dígito
                      b"ICMP:10.3.1.1:10.3.4.1:+16:42:8",
                      b"ICMP:10.3.1.1:10.3.4.1: 16:42:8"]:     # espaço também não
            self.malformado(dados)

    def test_endereco_invalido(self):
        for dados in [b"HELLO:10.3.1", b"HELLO:10.3.1.256", b"HELLO:abc", b"HELLO:",
                      b"HELLO:10.3.1.1.5", b"LSP:10.3.1:5:", b"LSP:10.3.1.1:5:10.3.2=1",
                      b"DADOS:10.3.1.1:destino:16:0:oi", b"ICMP:x:10.3.4.1:16:42:8"]:
            self.malformado(dados)

    def test_custo_zero(self):
        self.malformado(b"LSP:10.3.1.1:5:10.3.2.1=0")

    def test_item_do_lsp_mal_escrito(self):
        for dados in [b"LSP:10.3.1.1:5:10.3.2.1", b"LSP:10.3.1.1:5:10.3.2.1==1",
                      b"LSP:10.3.1.1:5:10.3.2.1=1=2"]:
            self.malformado(dados)

    def test_tipo_icmp_desconhecido(self):
        for tipo in (b"1", b"5", b"12"):
            self.malformado(b"ICMP:10.3.1.1:10.3.4.1:16:42:" + tipo)

    def test_fora_do_ascii(self):
        self.malformado("DADOS:10.3.1.1:10.3.4.1:16:0:Olá".encode("utf-8"))   # acento (D13)
        self.malformado(b"HELLO:10.3.1.1\xff")

    def test_so_um_fim_de_linha_tolerado(self):
        self.malformado(b"HELLO:10.3.1.1\n\n")
        self.malformado(b"HELLO: 10.3.1.1")


class TestFuncoesDeEndereco(unittest.TestCase):

    def test_is_virtual_addr(self):
        for bom in ["10.6.1.1", "0.0.0.0", "255.255.255.255", "127.0.0.1"]:
            self.assertTrue(is_virtual_addr(bom), bom)
        for ruim in ["10.6.1", "10.6.1.1.1", "10.6.1.256", "10.6..1", "", "a.b.c.d", "10.6.1.-1",
                     "10.6.1.+1", " 10.6.1.1", "10.6.1.²", "localhost"]:
            self.assertFalse(is_virtual_addr(ruim), ruim)

    def test_network_of(self):
        self.assertEqual(network_of("10.6.2.1"), "10.6.2.0/24")
        self.assertEqual(network_of("10.6.2.50"), "10.6.2.0/24")

    def test_same_network(self):
        self.assertTrue(same_network("10.7.1.1", "10.7.1.50"))   # exemplo do enunciado
        self.assertFalse(same_network("10.7.1.1", "10.7.2.1"))
        self.assertFalse(same_network("10.6.1.1", "10.7.1.1"))   # outro grupo

    def test_valid_text(self):
        self.assertTrue(valid_text("Oi pessoal!"))
        self.assertTrue(valid_text(""))
        self.assertFalse(valid_text("hora: 10h"))
        self.assertFalse(valid_text("Olá"))


if __name__ == "__main__":
    unittest.main()
