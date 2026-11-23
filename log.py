"""Logs em tempo real do roteador.

Dono: William. Ver docs/IMPLEMENTATION_PLAN.md §4.7.

Cada linha: '2026-11-19 16:01:02.123 [CATEGORIA] texto'.
Sempre gravada com flush imediato em logs/<endereço>.log (enunciado: "salvar em logs em tempo real")
e, se terminal=True, também mostrada no terminal (enunciado: "exibe nele ... os logs").
Só o HELLO usa terminal=False, para não poluir a demonstração (D34).

O arquivo é gravado na hora, mas o terminal é escrito por uma thread só dele, que tira as linhas de
uma fila (D50). Assim, se a saída do terminal parar (por exemplo, texto selecionado no console do
Windows), quem chamou log() não fica preso: HELLO, recepção e encaminhamento continuam funcionando.
Os textos de log devem ser ASCII, sem acentos (D39), como tudo o que vai para a tela.

Eventos que o enunciado exige no log: vizinho ativo/inativo, LSP novo recebido, recálculo da tabela,
pacote encaminhado (com próximo salto e TTL) e mensagem ICMP gerada.
"""

import os
import queue
import threading
import time

LIMITE_FILA = 10000  # linhas guardadas enquanto o terminal estiver parado; o arquivo guarda todas


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
        # Uma só thread escreve no terminal, na ordem em que as linhas entraram na fila (D50).
        self.fila = queue.Queue(LIMITE_FILA)
        threading.Thread(target=self.escrever_terminal, daemon=True).start()

    def escrever_terminal(self):
        """Thread do terminal: se o print ficar parado, só esta thread espera."""
        while True:
            texto = self.fila.get()
            try:
                print(texto, flush=True)
            except (OSError, ValueError):
                pass  # terminal fechado: o arquivo de log continua com tudo
            finally:
                self.fila.task_done()

    def mostrar(self, texto):
        """Põe um texto na fila do terminal, sem nunca esperar pelo terminal."""
        try:
            self.fila.put_nowait(texto)
        except queue.Full:
            pass  # terminal parado há muito tempo: descarta da tela, nunca trava o roteador

    def esperar_terminal(self, limite=2.0):
        """Espera a fila esvaziar, por no máximo 'limite' segundos (mantém a ordem na tela)."""
        fim = time.monotonic() + limite
        while self.fila.unfinished_tasks and time.monotonic() < fim:
            time.sleep(0.005)

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
                self.mostrar(linha)

    def close(self):
        """Mostra o que falta no terminal e fecha o arquivo (usado nos testes)."""
        self.esperar_terminal()
        with self.lock:
            self.arquivo.close()
