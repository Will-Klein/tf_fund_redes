"""Testes do log.py (dono: William)."""

import io
import os
import re
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout

from log import Logger

# Formato: 2026-11-19 16:01:02.123 [CATEGORIA] texto
FORMATO = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \[([A-Z]+)\] (.*)$")


class SaidaTravada(io.StringIO):
    """Saída que fica parada, como um terminal pausado, até 'liberar' ser acionado."""

    def __init__(self):
        super().__init__()
        self.liberar = threading.Event()

    def write(self, texto):
        self.liberar.wait(10)
        return super().write(texto)


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
            logger.esperar_terminal()
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
            logger.esperar_terminal()
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

    def test_terminal_parado_nao_trava_quem_registra(self):
        # D50: simula um terminal pausado (ex.: texto selecionado no console do Windows)
        logger = Logger(self.caminho)
        saida = SaidaTravada()
        with redirect_stdout(saida):
            inicio = time.monotonic()
            for i in range(50):
                logger.log("LSP", "linha %d" % i)
            logger.mostrar("Mensagem de 10.6.1.1 para 10.6.2.1: oi")
            self.assertLess(time.monotonic() - inicio, 1)      # quem registra não esperou o terminal
            self.assertEqual(len(self.ler_linhas()), 50)       # o arquivo segue em tempo real
            self.assertEqual(saida.getvalue(), "")             # e o terminal ainda não escreveu nada
            saida.liberar.set()
            logger.esperar_terminal(5)
        logger.close()
        linhas = saida.getvalue().splitlines()
        self.assertEqual(len(linhas), 51)                      # nada se perdeu
        self.assertEqual([l.split("] ")[1] for l in linhas[:50]], ["linha %d" % i for i in range(50)])
        self.assertEqual(linhas[50], "Mensagem de 10.6.1.1 para 10.6.2.1: oi")   # e a ordem foi mantida

    def test_espera_do_terminal_tem_limite(self):
        logger = Logger(self.caminho)
        saida = SaidaTravada()
        with redirect_stdout(saida):
            logger.mostrar("linha")
            inicio = time.monotonic()
            logger.esperar_terminal(0.1)
            self.assertLess(time.monotonic() - inicio, 1)
            saida.liberar.set()
            logger.esperar_terminal(5)
        logger.close()

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
