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

from packets import is_virtual_addr, so_digitos

DEFAULT_PORT = 6000  # enunciado: "porta UDP local ... (padrão: 6000)"

NeighborConf = namedtuple("NeighborConf", "ip port cost")
Config = namedtuple("Config", "address port neighbors")  # neighbors: lista de NeighborConf


class ConfigError(Exception):
    """Erro no arquivo de configuração (a mensagem inclui o número da linha)."""


def ler_porta(texto, num_linha):
    """Porta UDP: inteiro de 1 a 65535."""
    if not so_digitos(texto) or not 1 <= int(texto) <= 65535:
        raise ConfigError("linha %d: porta invalida %r (use um inteiro de 1 a 65535)" % (num_linha, texto))
    return int(texto)


def segue_padrao_do_trabalho(endereco):
    """True se o endereço tem a forma 10.G.R.1 (enunciado: 'endereço virtual 10.G.R.1')."""
    octetos = endereco.split(".")
    return octetos[0] == "10" and octetos[3] == "1"


def load_config(path):
    """Lê o arquivo em 'path' e devolve um Config. Levanta ConfigError se houver erro."""
    try:
        with open(path, encoding="utf-8") as arquivo:
            linhas = arquivo.readlines()
    except (OSError, UnicodeDecodeError) as erro:
        raise ConfigError("nao foi possivel ler %s: %s" % (path, erro))

    endereco = None
    porta = None
    vizinhos = []

    for num_linha, linha in enumerate(linhas, start=1):
        partes = linha.split("#")[0].split()  # tira o comentário e separa por espaços
        if not partes:
            continue  # linha vazia ou só comentário
        diretiva, args = partes[0], partes[1:]

        if diretiva == "endereco":
            if len(args) != 1:
                raise ConfigError("linha %d: use 'endereco <endereco virtual>'" % num_linha)
            if endereco is not None:
                raise ConfigError("linha %d: 'endereco' repetido" % num_linha)
            if not is_virtual_addr(args[0]):
                raise ConfigError("linha %d: endereco invalido %r (ex.: 10.6.1.1)" % (num_linha, args[0]))
            endereco = args[0]

        elif diretiva == "porta":
            if len(args) != 1:
                raise ConfigError("linha %d: use 'porta <porta UDP>'" % num_linha)
            if porta is not None:
                raise ConfigError("linha %d: 'porta' repetida" % num_linha)
            porta = ler_porta(args[0], num_linha)

        elif diretiva == "vizinho":
            if len(args) != 3:
                raise ConfigError("linha %d: use 'vizinho <IP real> <porta UDP> <custo>'" % num_linha)
            ip, texto_porta, texto_custo = args
            if not is_virtual_addr(ip):
                raise ConfigError("linha %d: IP do vizinho invalido %r (use o IP numerico, ex.: "
                                  "192.168.0.12)" % (num_linha, ip))
            porta_vizinho = ler_porta(texto_porta, num_linha)
            if not so_digitos(texto_custo) or int(texto_custo) <= 0:
                raise ConfigError("linha %d: custo invalido %r (use um inteiro positivo)"
                                  % (num_linha, texto_custo))
            for v in vizinhos:
                if (v.ip, v.port) == (ip, porta_vizinho):
                    raise ConfigError("linha %d: vizinho %s:%d repetido" % (num_linha, ip, porta_vizinho))
            vizinhos.append(NeighborConf(ip, porta_vizinho, int(texto_custo)))

        else:
            raise ConfigError("linha %d: diretiva desconhecida %r (use endereco, porta ou vizinho)"
                              % (num_linha, diretiva))

    if endereco is None:
        raise ConfigError("falta a linha 'endereco <endereco virtual>'")
    if porta is None:
        porta = DEFAULT_PORT
    if not segue_padrao_do_trabalho(endereco):
        # Só aviso: o roteador funciona, mas o enunciado pede endereços 10.G.R.1.
        print("Aviso: o endereco %s nao segue o padrao 10.G.R.1 do enunciado" % endereco)
    return Config(endereco, porta, vizinhos)
