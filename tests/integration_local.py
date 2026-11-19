"""Teste de integração: 5 roteadores reais (topologia local5) na mesma máquina.

Dono: William (F3). Rodar da raiz do repositório (leva ~1 minuto e usa as portas UDP 6001-6005):

    python3 tests/integration_local.py

Não é rodado pelo 'unittest discover' (o nome não começa com test_), porque é lento.

O script sobe os 5 roteadores como processos separados, digita comandos no terminal de cada um,
como uma pessoa faria, e compara com o esperado (docs/IMPLEMENTATION_PLAN.md §5):
  1. convergência: vizinhos, LSDB com 5 origens e tabelas;
  2. ping com TTL crescente, ping para rede inexistente e msg (precisa do forwarding.py);
  3. robustez: pacote de par desconhecido e pacote malformado;
  4. queda de R2: inatividade em ~20 s e rotas alternativas;
  5. reinício de R2: seq maior aceito, sincronização e tabelas de volta;
  6. 'sair' encerra todos.
Verificações que dependem de um módulo ainda não implementado aparecem como PULADO.
Os logs ficam numa pasta temporária, mostrada no início e no fim.
"""

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTER = os.path.join(RAIZ, "router.py")
LINHA_DE_LOG = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \[")

# Tabelas esperadas da local5 (plano §5): destino -> (próximo salto, custo), com R = 10.6.R.1
ESPERADA = {1: {2: (2, 1), 3: (2, 3), 4: (2, 8), 5: (2, 6)},
            2: {1: (1, 1), 3: (3, 2), 4: (4, 7), 5: (3, 5)},
            3: {1: (2, 3), 2: (2, 2), 4: (5, 8), 5: (5, 3)},
            4: {1: (2, 8), 2: (2, 7), 3: (5, 8), 5: (5, 5)},
            5: {1: (3, 6), 2: (3, 5), 3: (3, 3), 4: (4, 5)}}
SEM_R2 = {1: {3: (3, 4), 4: (3, 12), 5: (3, 7)},
          3: {1: (1, 4), 4: (5, 8), 5: (5, 3)},
          4: {1: (5, 12), 3: (5, 8), 5: (5, 5)},
          5: {1: (3, 7), 3: (3, 3), 4: (4, 5)}}
GRAU = {1: 2, 2: 3, 3: 3, 4: 2, 5: 2}   # número de vizinhos de cada roteador

FORWARDING_PENDENTE = "F2 (Leonardo)"   # texto do esboço do forwarding.py ainda não implementado


def end(n):
    return "10.6.%d.1" % n


def como_tabela(curta):
    """{3: (2, 3)} -> {'10.6.3.0/24': ('10.6.2.1', 3)}, o formato que o comando 'tabela' mostra."""
    return {"10.6.%d.0/24" % d: (end(p), c) for d, (p, c) in curta.items()}


def comando_roteador(conf):
    """Comando que sobe um roteador (separado em função para poder ser trocado em verificações)."""
    return [sys.executable, "-u", ROUTER, conf]


class Roteador:
    """Um roteador rodando em outro processo; a saída do terminal dele é guardada linha a linha."""

    def __init__(self, n, pasta):
        self.n = n
        self.pasta = pasta
        conf = os.path.join(RAIZ, "configs", "local5", "r%d.conf" % n)
        self.proc = subprocess.Popen(comando_roteador(conf), cwd=pasta, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     universal_newlines=True, bufsize=1)
        self.saida = []
        self.trava = threading.Lock()
        threading.Thread(target=self.ler_saida, daemon=True).start()

    def ler_saida(self):
        for linha in self.proc.stdout:
            with self.trava:
                self.saida.append(linha.rstrip("\n"))

    def vivo(self):
        return self.proc.poll() is None

    def comando(self, texto, espera=0.7):
        """Digita um comando e devolve as linhas de resposta (sem as linhas de log e sem o '> ')."""
        with self.trava:
            inicio = len(self.saida)
        self.proc.stdin.write(texto + "\n")
        self.proc.stdin.flush()
        time.sleep(espera)
        with self.trava:
            novas = self.saida[inicio:]
        respostas = []
        for linha in novas:
            while linha.startswith("> "):
                linha = linha[2:]
            if linha.strip() and not LINHA_DE_LOG.match(linha):
                respostas.append(linha)
        return respostas

    def tabela(self):
        resultado = {}
        for linha in self.comando("tabela"):
            partes = linha.split()
            if len(partes) == 3 and partes[0].endswith("/24"):
                resultado[partes[0]] = (partes[1], int(partes[2]))
        return resultado

    def lsdb(self):
        """{origem: seq}"""
        resultado = {}
        for linha in self.comando("lsdb"):
            partes = linha.split()
            if len(partes) >= 3 and partes[0].startswith("10.") and partes[1].isdigit():
                resultado[partes[0]] = int(partes[1])
        return resultado

    def vizinhos(self):
        return [linha.split()[0] for linha in self.comando("vizinhos")
                if len(linha.split()) == 3 and linha.startswith("10.")]

    def log(self):
        caminho = os.path.join(self.pasta, "logs", end(self.n) + ".log")
        if not os.path.exists(caminho):
            return ""
        with open(caminho, encoding="utf-8") as arquivo:
            return arquivo.read()

    def tudo_que_mostrou(self):
        with self.trava:
            return "\n".join(self.saida)


resultados = []   # [(situação, descrição)]


def registrar(situacao, descricao, detalhe=""):
    resultados.append((situacao, descricao))
    print("[%s] %s%s" % (situacao, descricao, ("\n         " + detalhe) if detalhe else ""), flush=True)


def verificar(descricao, ok, detalhe=""):
    registrar("OK" if ok else "FALHOU", descricao, "" if ok else detalhe)
    return ok


def esperar_ate(condicao, limite):
    """Repete condicao() a cada segundo até ela ser verdadeira ou passar 'limite' segundos."""
    fim = time.time() + limite
    while True:
        if condicao():
            return True
        if time.time() > fim:
            return False
        time.sleep(1)


# ---------------------------------------------------------------------- etapas

def etapa_partida(rs):
    time.sleep(2)
    mortos = [r for r in rs.values() if not r.vivo()]
    for r in mortos:
        verificar("R%d iniciou" % r.n, False, "o processo terminou:\n" + r.tudo_que_mostrou()[-800:])
    return not mortos


def etapa_convergencia(rs):
    print("\n== 1. Convergencia (espera ate 20 s)")
    t0 = time.time()
    convergiu = esperar_ate(lambda: all(r.tabela() == como_tabela(ESPERADA[n]) for n, r in rs.items()), 20)
    tempo = time.time() - t0   # medido aqui, antes das conferências abaixo (que levam ~10 s)
    for n, r in rs.items():
        tabela = r.tabela()
        verificar("R%d: tabela igual a do plano" % n, tabela == como_tabela(ESPERADA[n]),
                  "obtida %s\n         esperada %s" % (tabela, como_tabela(ESPERADA[n])))
        verificar("R%d: %d vizinhos ativos" % (n, GRAU[n]), len(r.vizinhos()) == GRAU[n])
        verificar("R%d: LSDB com as 5 origens" % n, sorted(r.lsdb()) == [end(i) for i in range(1, 6)])
    if convergiu:
        print("   convergiu em ate %.0f s (precisao de alguns segundos; o instante exato esta nos logs)" % tempo)


def etapa_ping_e_msg(rs):
    print("\n== 2. ping e msg (R1 -> R5, caminho R1-R2-R3-R5)")
    r1, r5 = rs[1], rs[5]
    primeira = " ".join(r1.comando("ping 10.6.5.1 1", espera=2.5))
    if FORWARDING_PENDENTE in primeira:
        registrar("PULADO", "ping, msg e logs de encaminhamento: forwarding.py ainda nao implementado")
        return
    verificar("ping TTL 1: tempo excedido em R2", "Tempo excedido informado por 10.6.2.1" in primeira, primeira)
    casos = [("ping 10.6.5.1 2", "Tempo excedido informado por 10.6.3.1", "ping TTL 2: tempo excedido em R3"),
             ("ping 10.6.5.1 3", "Resposta de eco de 10.6.5.1", "ping TTL 3: eco de R5"),
             ("ping 10.6.5.1", "Resposta de eco de 10.6.5.1", "ping TTL padrao (16): eco de R5"),
             ("ping 10.6.5.77", "Resposta de eco de 10.6.5.77",
              "ping a outro host da rede de R5: responde como o endereco pingado"),
             ("ping 10.99.99.1", "Destino inalcancavel: sem rota", "ping para rede inexistente"),
             ("msg 10.6.5.1 teste de integracao", "DADOS enviado para 10.6.5.1 via 10.6.2.1", "msg enviada via R2")]
    for linha, esperado, descricao in casos:
        texto = " ".join(r1.comando(linha, espera=2.5))
        verificar(descricao, esperado in texto, texto)
    verificar("R5 mostrou a mensagem com origem e destino",
              "Mensagem de 10.6.1.1 para 10.6.5.1: teste de integracao" in r5.tudo_que_mostrou())
    verificar("log de R2 registra pacote encaminhado", "[ENCAMINHA]" in rs[2].log())
    verificar("log de R2 registra ICMP gerado (tempo excedido)", "[ICMP]" in rs[2].log())


def etapa_robustez(rs):
    print("\n== 3. Robustez: par desconhecido")
    estranho = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    estranho.sendto(b"HELLO:10.6.9.1", ("127.0.0.1", 6001))
    estranho.close()
    time.sleep(0.5)
    verificar("R1 descartou pacote de par desconhecido", "par desconhecido" in rs[1].log())
    verificar("R1 continua respondendo", rs[1].tabela() == como_tabela(ESPERADA[1]))


def etapa_queda(rs):
    print("\n== 4. Queda de R2 (espera ate 30 s)")
    rs[2].proc.kill()
    rs[2].proc.wait()
    t_queda = time.time()

    # Com R2 fora do ar, a porta 6002 fica livre: dali sai um pacote "do vizinho R2", malformado
    falso_r2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    falso_r2.bind(("127.0.0.1", 6002))
    for lixo in [b"LSP:10.6.2.1:abc:", b"OLA:10.6.2.1", b"HELLO"]:
        falso_r2.sendto(lixo, ("127.0.0.1", 6001))
    falso_r2.close()
    time.sleep(0.5)
    verificar("R1 descartou pacotes malformados de um vizinho e continua vivo",
              "malformado" in rs[1].log() and rs[1].vivo())

    reconvergiu = esperar_ate(lambda: rs[1].tabela() == como_tabela(SEM_R2[1]), 30)
    tempo = time.time() - t_queda
    verificar("R1 detectou R2 inativo", "10.6.2.1 (127.0.0.1:6002) ficou INATIVO" in rs[1].log())
    verificar("R1 usa as rotas alternativas via R3 (em %.0f s)" % tempo, reconvergiu,
              "tabela de R1: %s" % rs[1].tabela())
    esperar_ate(lambda: all(rs[n].tabela() == como_tabela(SEM_R2[n]) for n in [3, 4, 5]), 10)
    for n in [3, 4, 5]:
        verificar("R%d: tabela sem R2 igual a esperada" % n, rs[n].tabela() == como_tabela(SEM_R2[n]),
                  "obtida %s" % rs[n].tabela())


def etapa_reinicio(rs, pasta):
    print("\n== 5. Reinicio de R2 (espera ate 20 s)")
    seq_antigo = rs[1].lsdb().get(end(2))   # o LSP antigo de R2 continua na LSDB até envelhecer
    rs[2] = Roteador(2, pasta)
    voltou = esperar_ate(lambda: all(r.tabela() == como_tabela(ESPERADA[n]) for n, r in rs.items()), 20)
    verificar("todas as tabelas voltaram ao estado inicial", voltou)
    seq_novo = rs[1].lsdb().get(end(2))
    verificar("R1 aceitou o LSP de R2 reiniciado com seq maior (%s -> %s)" % (seq_antigo, seq_novo),
              seq_antigo is not None and seq_novo is not None and seq_novo > seq_antigo)
    verificar("R2 reiniciado recebeu a sincronizacao (LSDB com as 5 origens)",
              sorted(rs[2].lsdb()) == [end(i) for i in range(1, 6)])


def etapa_sair(rs):
    print("\n== 6. sair")
    for r in rs.values():
        r.proc.stdin.write("sair\n")
        r.proc.stdin.flush()
    for n, r in rs.items():
        try:
            codigo = r.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            codigo = None
        verificar("R%d encerrou com 'sair'" % n, codigo == 0, "codigo de saida: %s" % codigo)


def main():
    pasta = tempfile.mkdtemp(prefix="integracao_local5_")
    print("Logs desta execucao em:", os.path.join(pasta, "logs"))
    rs = {n: Roteador(n, pasta) for n in range(1, 6)}
    try:
        if etapa_partida(rs):
            etapa_convergencia(rs)
            etapa_ping_e_msg(rs)
            etapa_robustez(rs)
            etapa_queda(rs)
            etapa_reinicio(rs, pasta)
            etapa_sair(rs)
    finally:
        for r in rs.values():
            if r.vivo():
                r.proc.kill()
    contagem = {s: sum(1 for x, _ in resultados if x == s) for s in ["OK", "FALHOU", "PULADO"]}
    print("\nResumo: %(OK)d OK, %(FALHOU)d FALHOU, %(PULADO)d PULADO" % contagem)
    print("Logs em:", os.path.join(pasta, "logs"))
    sys.exit(1 if contagem["FALHOU"] or not resultados else 0)


if __name__ == "__main__":
    main()
