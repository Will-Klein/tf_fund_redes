"""Formato e leitura dos pacotes do trabalho.

Dono: Leonardo (fase F1). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.1.

Toda comunicação é texto ASCII com campos separados por ':' (enunciado, "Formato dos pacotes"):

    HELLO:<endereço virtual>                                   ex.: HELLO:10.3.1.1
    LSP:<origem>:<seq>:<vizinho>=<custo>;<vizinho>=<custo>;... ex.: LSP:10.3.1.1:1767712000:10.3.2.1=1;10.3.4.1=3
    DADOS:<origem>:<destino>:<TTL>:<id>:<mensagem>             ex.: DADOS:10.3.1.1:10.3.4.1:16:0:Oi pessoal!
    ICMP:<origem>:<destino>:<TTL>:<id>:<tipo>                  ex.: ICMP:10.3.1.1:10.3.4.1:16:42:8

LSP sem vizinhos ativos tem a lista vazia: LSP:10.3.1.1:1767712001:

Regras de leitura (RF04, D12, D13):
- Malformado (levanta MalformedPacket): bytes fora do ASCII, tipo desconhecido, número errado de
  campos, campo numérico que não é só dígitos, endereço que não é IPv4 válido, custo <= 0,
  tipo ICMP fora de {0, 3, 8, 11}, mensagem com ':' (vira campo a mais) ou fora do ASCII.
- Tolerado: '\\n' ou '\\r\\n' no fim do datagrama; itens vazios na lista do LSP (ex.: ';' no fim).
- encode() sempre gera o formato exato, sem essas sobras.
"""

from collections import namedtuple

# Um tipo para cada pacote. Os nomes dos campos seguem o enunciado.
Hello = namedtuple("Hello", "addr")
Lsp = namedtuple("Lsp", "origin seq neighbors")  # neighbors: dict {endereço virtual: custo}
Dados = namedtuple("Dados", "src dst ttl id msg")
Icmp = namedtuple("Icmp", "src dst ttl id type")

# Tipos de mensagem ICMP (tabela "Tipos de mensagem ICMP" do enunciado)
ICMP_ECHO_REPLY = 0        # resposta de eco
ICMP_DEST_UNREACHABLE = 3  # destino inalcançável
ICMP_ECHO_REQUEST = 8      # pedido de eco
ICMP_TIME_EXCEEDED = 11    # tempo excedido


class MalformedPacket(Exception):
    """Pacote malformado: deve ser descartado sem derrubar o roteador (RF04)."""


def parse(data):
    """Converte os bytes recebidos em Hello, Lsp, Dados ou Icmp.

    Levanta MalformedPacket se o pacote não seguir o formato do enunciado.
    """
    raise NotImplementedError("packets.parse: F1 (Leonardo)")


def encode(pkt):
    """Converte um Hello, Lsp, Dados ou Icmp em bytes no formato exato do enunciado."""
    raise NotImplementedError("packets.encode: F1 (Leonardo)")


def is_virtual_addr(s):
    """True se s é um endereço IPv4 com 4 octetos de 0 a 255 (ex.: '10.6.2.1')."""
    raise NotImplementedError("packets.is_virtual_addr: F1 (Leonardo)")


def network_of(addr):
    """Rede /24 de um endereço: '10.6.2.1' -> '10.6.2.0/24'."""
    raise NotImplementedError("packets.network_of: F1 (Leonardo)")


def same_network(a, b):
    """True se os dois endereços estão na mesma rede /24 (3 primeiros octetos iguais)."""
    raise NotImplementedError("packets.same_network: F1 (Leonardo)")


def valid_text(msg):
    """True se a mensagem de DADOS é válida: só caracteres ASCII e sem ':' (D13)."""
    raise NotImplementedError("packets.valid_text: F1 (Leonardo)")
