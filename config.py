"""Leitura e validação do arquivo de configuração do roteador.

Dono: William (fase F1). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §3 e §4.2.

Formato (D03): texto, uma diretiva por linha, '#' inicia comentário, linhas vazias ignoradas.

    # Roteador 1 do grupo 6
    endereco 10.6.1.1
    porta 6000                      # opcional; padrão 6000
    # vizinho <IP real> <porta UDP> <custo>
    vizinho 192.168.0.12 6000 1

Validação (erro com o número da linha; o roteador não inicia):
- 'endereco' obrigatório e IPv4 válido (só aviso se não seguir o padrão 10.G.R.1);
- porta de 1 a 65535;
- IP do vizinho é IPv4 literal (não aceita nome de máquina);
- custo é inteiro > 0 (enunciado: "custo do enlace (inteiro positivo)");
- par (IP, porta) repetido é erro.
"""

from collections import namedtuple

DEFAULT_PORT = 6000  # enunciado: "porta UDP local ... (padrão: 6000)"

NeighborConf = namedtuple("NeighborConf", "ip port cost")
Config = namedtuple("Config", "address port neighbors")  # neighbors: lista de NeighborConf


class ConfigError(Exception):
    """Erro no arquivo de configuração (a mensagem inclui o número da linha)."""


def load_config(path):
    """Lê o arquivo em 'path' e devolve um Config. Levanta ConfigError se houver erro."""
    raise NotImplementedError("config.load_config: F1 (William)")
