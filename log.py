"""Logs em tempo real do roteador.

Dono: William (fase F1). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.7.

Cada linha: '2026-11-19 16:01:02.123 [CATEGORIA] texto'.
Sempre gravada com flush imediato em logs/<endereço>.log (enunciado: "salvar em logs em tempo real")
e, se terminal=True, também mostrada no terminal (enunciado: "exibe nele ... os logs").
Só o HELLO usa terminal=False, para não poluir a demonstração (D34).

Eventos que o enunciado exige no log: vizinho ativo/inativo, LSP novo recebido, recálculo da tabela,
pacote encaminhado (com próximo salto e TTL) e mensagem ICMP gerada.
"""


class Logger:
    def __init__(self, path):
        """Abre (criando a pasta, se preciso) o arquivo de log em 'path'."""
        self.path = path

    def log(self, categoria, texto, terminal=True):
        """Registra uma linha com data e hora em milissegundos. Pode ser chamado por várias threads."""
        raise NotImplementedError("Logger.log: F1 (William)")
