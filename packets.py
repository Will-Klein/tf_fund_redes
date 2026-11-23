"""Formato e leitura dos pacotes do trabalho.

Dono: William (fase F1). Interface fixada na F0; ver docs/IMPLEMENTATION_PLAN.md §4.1.

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
TIPOS_ICMP = (ICMP_ECHO_REPLY, ICMP_DEST_UNREACHABLE, ICMP_ECHO_REQUEST, ICMP_TIME_EXCEEDED)

# Maior quantidade de dígitos aceita num campo numérico. 20 dígitos cobrem qualquer inteiro de 64 bits.
# Sem esse limite, a partir do Python 3.11 o int() levanta ValueError com mais de 4300 dígitos (D51).
MAX_DIGITOS = 20

# Quantos campos cada tipo de pacote tem depois do split(':'), contando o próprio tipo
NUM_CAMPOS = {"HELLO": 2, "LSP": 4, "DADOS": 6, "ICMP": 6}


class MalformedPacket(Exception):
    """Pacote malformado: deve ser descartado sem derrubar o roteador (RF04)."""


# ---------------------------------------------------------------------------------------------
# Funções auxiliares de validação
# ---------------------------------------------------------------------------------------------

def so_digitos(texto):
    """True se o texto tem só os dígitos 0-9, e no máximo MAX_DIGITOS deles.

    Não usamos str.isdigit(), que aceita '²', nem int() direto, que aceita '+5', ' 5' e '-5'.
    """
    return 0 < len(texto) <= MAX_DIGITOS and all(c in "0123456789" for c in texto)


def is_virtual_addr(s):
    """True se s é um endereço IPv4 com 4 octetos de 0 a 255 (ex.: '10.6.2.1')."""
    octetos = s.split(".")
    if len(octetos) != 4:
        return False
    for octeto in octetos:
        if not so_digitos(octeto) or int(octeto) > 255:
            return False
    return True


def network_of(addr):
    """Rede /24 de um endereço: '10.6.2.1' -> '10.6.2.0/24'."""
    a, b, c, _ = addr.split(".")
    return "%s.%s.%s.0/24" % (a, b, c)


def same_network(a, b):
    """True se os dois endereços estão na mesma rede /24 (3 primeiros octetos iguais)."""
    return a.split(".")[:3] == b.split(".")[:3]


def valid_text(msg):
    """True se a mensagem de DADOS é válida: só caracteres ASCII e sem ':' (D13)."""
    for c in msg:
        if ord(c) > 127 or c == ":":
            return False
    return True


def ler_numero(texto, nome):
    """Converte um campo numérico. Levanta MalformedPacket se não for só dígitos."""
    if not so_digitos(texto):
        raise MalformedPacket("%s nao numerico: %r" % (nome, texto))
    return int(texto)


def ler_endereco(texto, nome):
    """Confere um campo de endereço virtual. Levanta MalformedPacket se não for IPv4 válido."""
    if not is_virtual_addr(texto):
        raise MalformedPacket("%s nao e um endereco valido: %r" % (nome, texto))
    return texto


def ler_lista_lsp(texto):
    """'10.3.2.1=1;10.3.4.1=3' -> {'10.3.2.1': 1, '10.3.4.1': 3}. Lista vazia '' -> {}."""
    vizinhos = {}
    for item in texto.split(";"):
        if item == "":
            continue  # tolerância D12: ';' no fim ou lista vazia
        partes = item.split("=")
        if len(partes) != 2:
            raise MalformedPacket("item da lista do LSP sem 'vizinho=custo': %r" % item)
        vizinho = ler_endereco(partes[0], "vizinho do LSP")
        custo = ler_numero(partes[1], "custo")
        if custo <= 0:
            raise MalformedPacket("custo deve ser inteiro positivo: %r" % item)
        vizinhos[vizinho] = custo
    return vizinhos


# ---------------------------------------------------------------------------------------------
# Leitura (bytes -> pacote) e escrita (pacote -> bytes)
# ---------------------------------------------------------------------------------------------

def parse(data):
    """Converte os bytes recebidos em Hello, Lsp, Dados ou Icmp.

    Levanta MalformedPacket se o pacote não seguir o formato do enunciado.
    """
    # 1. Texto ASCII (enunciado: "mensagens em texto ASCII"). Acento -> erro -> malformado.
    try:
        texto = data.decode("ascii")
    except UnicodeDecodeError:
        raise MalformedPacket("bytes fora do ASCII")

    # 2. Tolerância D12: aceita um '\r\n' ou '\n' no fim (outras implementações podem mandar).
    if texto.endswith("\r\n"):
        texto = texto[:-2]
    elif texto.endswith("\n"):
        texto = texto[:-1]

    # 3. Tipo conhecido e número exato de campos (enunciado: "tipo desconhecido, número errado
    #    de campos"). Uma mensagem de DADOS com ':' vira campo a mais e cai aqui (D13).
    campos = texto.split(":")
    tipo = campos[0]
    if tipo not in NUM_CAMPOS:
        raise MalformedPacket("tipo desconhecido: %r" % tipo)
    if len(campos) != NUM_CAMPOS[tipo]:
        raise MalformedPacket("%s com %d campos (esperado %d)" % (tipo, len(campos), NUM_CAMPOS[tipo]))

    # 4. Cada campo no seu formato (enunciado: "valores não numéricos").
    if tipo == "HELLO":
        return Hello(ler_endereco(campos[1], "endereco"))

    if tipo == "LSP":
        return Lsp(ler_endereco(campos[1], "origem"),
                   ler_numero(campos[2], "seq"),
                   ler_lista_lsp(campos[3]))

    origem = ler_endereco(campos[1], "origem")
    destino = ler_endereco(campos[2], "destino")
    ttl = ler_numero(campos[3], "TTL")
    ident = ler_numero(campos[4], "id")

    if tipo == "DADOS":
        # A mensagem já é ASCII (passo 1) e não tem ':' (passo 3): é válida (D13).
        return Dados(origem, destino, ttl, ident, campos[5])

    tipo_icmp = ler_numero(campos[5], "tipo ICMP")
    if tipo_icmp not in TIPOS_ICMP:
        raise MalformedPacket("tipo ICMP desconhecido: %d" % tipo_icmp)
    return Icmp(origem, destino, ttl, ident, tipo_icmp)


def encode(pkt):
    """Converte um Hello, Lsp, Dados ou Icmp em bytes no formato exato do enunciado.

    Quem chama garante que o pacote é válido (ex.: a CLI confere a mensagem com valid_text).
    """
    if isinstance(pkt, Hello):
        texto = "HELLO:%s" % pkt.addr
    elif isinstance(pkt, Lsp):
        lista = ";".join("%s=%d" % (vizinho, custo) for vizinho, custo in pkt.neighbors.items())
        texto = "LSP:%s:%d:%s" % (pkt.origin, pkt.seq, lista)
    elif isinstance(pkt, Dados):
        texto = "DADOS:%s:%s:%d:%d:%s" % (pkt.src, pkt.dst, pkt.ttl, pkt.id, pkt.msg)
    elif isinstance(pkt, Icmp):
        texto = "ICMP:%s:%s:%d:%d:%d" % (pkt.src, pkt.dst, pkt.ttl, pkt.id, pkt.type)
    else:
        raise TypeError("encode: pacote de tipo desconhecido: %r" % (pkt,))
    return texto.encode("ascii")
