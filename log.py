"""Logs em tempo real do roteador.

Dono: William. Ver docs/IMPLEMENTATION_PLAN.md §4.7.

Cada linha: '2026-11-19 16:01:02.123 [CATEGORIA] texto'.
Sempre gravada com flush imediato em logs/<endereço>.log (enunciado: "salvar em logs em tempo real")
e, se terminal=True, também mostrada no terminal (enunciado: "exibe nele ... os logs").
Só o HELLO usa terminal=False, para não poluir a demonstração (D34).
Os textos de log devem ser ASCII, sem acentos (D39), como tudo o que vai para a tela.

Eventos que o enunciado exige no log: vizinho ativo/inativo, LSP novo recebido, recálculo da tabela,
pacote encaminhado (com próximo salto e TTL) e mensagem ICMP gerada.
"""

import os
import threading
import time


class Logger:
    def __init__(self, path):
        """Abre o arquivo de log em 'path' (criando a pasta, se preciso).

        O arquivo é aberto para acrescentar ('a'): ao reiniciar o roteador, o histórico anterior
        continua lá, o que ajuda a medir a convergência no relatório (D37).
        """
        self.path = path
        pasta = os.path.dirname(path)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        self.arquivo = open(path, "a", encoding="utf-8")
        # Várias threads (recepção, temporizador, CLI) escrevem no log: o lock evita linhas misturadas.
        self.lock = threading.Lock()

    def log(self, categoria, texto, terminal=True):
        """Registra uma linha com data e hora em milissegundos."""
        agora = time.time()
        milissegundos = int((agora % 1) * 1000)
        carimbo = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(agora))
        linha = "%s.%03d [%s] %s" % (carimbo, milissegundos, categoria, texto)
        with self.lock:
            self.arquivo.write(linha + "\n")
            self.arquivo.flush()  # tempo real: a linha vai para o disco na hora
            if terminal:
                print(linha, flush=True)

    def close(self):
        """Fecha o arquivo (usado ao encerrar e nos testes)."""
        with self.lock:
            self.arquivo.close()
