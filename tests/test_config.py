"""Testes do config.py (dono: William): arquivo válido, porta padrão e cada erro de validação."""

import glob
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from config import DEFAULT_PORT, Config, ConfigError, NeighborConf, load_config

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConfig(unittest.TestCase):

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.pasta.cleanup()

    def carregar(self, texto):
        """Grava 'texto' num arquivo temporário e chama load_config. Devolve (Config, o que foi impresso)."""
        caminho = os.path.join(self.pasta.name, "r.conf")
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        saida = io.StringIO()
        with redirect_stdout(saida):
            cfg = load_config(caminho)
        return cfg, saida.getvalue()

    def erro(self, texto, trecho):
        """Confere que o arquivo dá ConfigError e que a mensagem contém 'trecho' (ex.: a linha)."""
        with self.assertRaises(ConfigError) as ctx:
            self.carregar(texto)
        self.assertIn(trecho, str(ctx.exception))

    # --- arquivos válidos ---

    def test_arquivo_completo(self):
        cfg, saida = self.carregar(
            "# Roteador 1 do grupo 6 (comentário com acento)\n"
            "endereco 10.6.1.1\n"
            "porta 6001          # porta local\n"
            "\n"
            "# vizinho <IP real> <porta UDP> <custo>\n"
            "vizinho 192.168.0.12 6000 1   # R2\n"
            "   vizinho   192.168.0.13\t6000   5\n")
        self.assertEqual(cfg, Config("10.6.1.1", 6001, [NeighborConf("192.168.0.12", 6000, 1),
                                                        NeighborConf("192.168.0.13", 6000, 5)]))
        self.assertEqual(saida, "")   # endereço no padrão: nenhum aviso

    def test_arquivo_salvo_pelo_bloco_de_notas(self):
        # Windows (VDI): marca BOM no início e fim de linha CRLF
        caminho = os.path.join(self.pasta.name, "bom.conf")
        with open(caminho, "w", encoding="utf-8-sig", newline="\r\n") as arquivo:
            arquivo.write("# Roteador 1\nendereco 10.6.1.1\nporta 6000\nvizinho 10.20.30.40 6000 5\n")
        self.assertEqual(load_config(caminho),
                         Config("10.6.1.1", 6000, [NeighborConf("10.20.30.40", 6000, 5)]))

    def test_porta_padrao_6000(self):
        cfg, _ = self.carregar("endereco 10.6.1.1\nvizinho 127.0.0.1 6002 1\n")
        self.assertEqual(cfg.port, DEFAULT_PORT)
        self.assertEqual(cfg.port, 6000)

    def test_tipos_dos_campos(self):
        cfg, _ = self.carregar("endereco 10.6.1.1\nvizinho 127.0.0.1 6002 3\n")
        self.assertIsInstance(cfg.port, int)
        self.assertIsInstance(cfg.neighbors[0].port, int)
        self.assertIsInstance(cfg.neighbors[0].cost, int)

    def test_mesmo_ip_portas_diferentes(self):
        # topologia local5: todos em 127.0.0.1, a porta diferencia
        cfg, _ = self.carregar("endereco 10.6.1.1\nvizinho 127.0.0.1 6002 1\nvizinho 127.0.0.1 6003 4\n")
        self.assertEqual(len(cfg.neighbors), 2)

    def test_aviso_fora_do_padrao(self):
        cfg, saida = self.carregar("endereco 192.168.0.5\n")
        self.assertEqual(cfg.address, "192.168.0.5")   # só aviso, o roteador inicia
        self.assertIn("Aviso", saida)
        self.assertTrue(all(ord(c) < 128 for c in saida))   # D39

    def test_configs_do_repositorio(self):
        for caminho in sorted(glob.glob(os.path.join(RAIZ, "configs", "local5", "r*.conf"))):
            cfg = load_config(caminho)
            self.assertTrue(cfg.address.startswith("10.6."), caminho)
            self.assertGreater(len(cfg.neighbors), 0, caminho)

    def test_configs_do_grupo_avisam_do_ip_a_trocar(self):
        # configs/grupo tem marcadores IP_Rn: sem trocar pelo IP real, o roteador não inicia
        with self.assertRaises(ConfigError) as ctx:
            load_config(os.path.join(RAIZ, "configs", "grupo", "r1.conf"))
        self.assertIn("IP_R2", str(ctx.exception))

    # --- erros (cada um com o número da linha) ---

    def test_sem_endereco(self):
        self.erro("porta 6000\nvizinho 127.0.0.1 6002 1\n", "endereco")

    def test_endereco_invalido(self):
        self.erro("endereco 10.6.1\n", "linha 1")
        self.erro("endereco 10.6.1.300\n", "linha 1")
        self.erro("# c\nendereco 10.6.1.1 10.6.2.1\n", "linha 2")

    def test_endereco_repetido(self):
        self.erro("endereco 10.6.1.1\nendereco 10.6.2.1\n", "linha 2")

    def test_porta_invalida(self):
        for porta in ["0", "65536", "abc", "-1", "+6000"]:
            self.erro("endereco 10.6.1.1\nporta %s\n" % porta, "linha 2")
        self.erro("endereco 10.6.1.1\nporta\n", "linha 2")

    def test_numero_gigante_na_config(self):
        # D51: vira erro com o número da linha, em qualquer versão do Python
        grande = "9" * 5000
        self.erro("endereco 10.6.1.1\nporta %s\n" % grande, "linha 2")
        self.erro("endereco 10.6.1.1\nvizinho 127.0.0.1 6002 %s\n" % grande, "linha 2")
        self.erro("endereco 10.%s.1.1\n" % grande, "linha 1")

    def test_porta_repetida(self):
        self.erro("endereco 10.6.1.1\nporta 6000\nporta 6001\n", "linha 3")

    def test_ip_do_vizinho_invalido(self):
        self.erro("endereco 10.6.1.1\nvizinho localhost 6000 1\n", "linha 2")   # nome de máquina
        self.erro("endereco 10.6.1.1\nvizinho 192.168.0 6000 1\n", "linha 2")

    def test_porta_do_vizinho_invalida(self):
        self.erro("endereco 10.6.1.1\nvizinho 127.0.0.1 70000 1\n", "linha 2")

    def test_custo_invalido(self):
        for custo in ["0", "-1", "1.5", "um"]:
            self.erro("endereco 10.6.1.1\nvizinho 127.0.0.1 6002 %s\n" % custo, "linha 2")

    def test_vizinho_com_campos_faltando(self):
        self.erro("endereco 10.6.1.1\nvizinho 127.0.0.1 6002\n", "linha 2")
        self.erro("endereco 10.6.1.1\nvizinho 127.0.0.1 6002 1 9\n", "linha 2")

    def test_vizinho_repetido(self):
        self.erro("endereco 10.6.1.1\nvizinho 127.0.0.1 6002 1\nvizinho 127.0.0.1 6002 3\n", "linha 3")

    def test_diretiva_desconhecida(self):
        self.erro("endereco 10.6.1.1\nvizinhos 127.0.0.1 6002 1\n", "linha 2")

    def test_arquivo_inexistente(self):
        with self.assertRaises(ConfigError):
            load_config(os.path.join(self.pasta.name, "nao_existe.conf"))


if __name__ == "__main__":
    unittest.main()
