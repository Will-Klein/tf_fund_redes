"""Testes do log.py (dono: William)."""

import io
import os
import re
import tempfile
import threading
import unittest
from contextlib import redirect_stdout

from log import Logger

# Formato: 2026-11-19 16:01:02.123 [CATEGORIA] texto
FORMATO = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \[([A-Z]+)\] (.*)$")


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "logs", "10.6.1.1.log")

    def tearDown(self):
        self.pasta.cleanup()

    def ler_linhas(self):
        with open(self.caminho, encoding="utf-8") as arquivo:
            return arquivo.read().splitlines()

    def test_cria_pasta_e_grava_no_formato(self):
        logger = Logger(self.caminho)
        with redirect_stdout(io.StringIO()):
            logger.log("VIZINHO", "10.6.2.1 (127.0.0.1:6002) ficou ATIVO")
        # Lido ANTES de fechar: prova que a linha já está no disco (tempo real)
        linhas = self.ler_linhas()
        logger.close()
        self.assertEqual(len(linhas), 1)
        casamento = FORMATO.match(linhas[0])
        self.assertIsNotNone(casamento, linhas[0])
        self.assertEqual(casamento.group(1), "VIZINHO")
        self.assertEqual(casamento.group(2), "10.6.2.1 (127.0.0.1:6002) ficou ATIVO")

    def test_terminal_true_e_false(self):
        logger = Logger(self.caminho)
        saida = io.StringIO()
        with redirect_stdout(saida):
            logger.log("TABELA", "tabela recalculada", terminal=True)
            logger.log("HELLO", "HELLO enviado", terminal=False)
        logger.close()
        self.assertIn("[TABELA] tabela recalculada", saida.getvalue())
        self.assertNotIn("HELLO", saida.getvalue())   # HELLO não vai para o terminal (D34)
        self.assertEqual(len(self.ler_linhas()), 2)    # mas os dois estão no arquivo

    def test_reinicio_acrescenta_ao_arquivo(self):
        with redirect_stdout(io.StringIO()):
            primeiro = Logger(self.caminho)
            primeiro.log("LSP", "antes do reinício")
            primeiro.close()
            segundo = Logger(self.caminho)
            segundo.log("LSP", "depois do reinício")
            segundo.close()
        self.assertEqual(len(self.ler_linhas()), 2)    # D37: histórico preservado

    def test_varias_threads_nao_misturam_linhas(self):
        logger = Logger(self.caminho)

        def escrever(numero):
            for i in range(200):
                logger.log("ENCAMINHA", "thread %d linha %d" % (numero, i), terminal=False)

        threads = [threading.Thread(target=escrever, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        logger.close()
        linhas = self.ler_linhas()
        self.assertEqual(len(linhas), 800)
        for linha in linhas:
            self.assertIsNotNone(FORMATO.match(linha), linha)


if __name__ == "__main__":
    unittest.main()
