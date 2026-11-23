"""Experimentos do relatório (Q1 a Q6) com os 5 roteadores reais da topologia local5.

Cada experimento sobe os roteadores em processos separados, captura o tráfego da loopback em .pcapng
(capturas/) e guarda os logs e os números medidos (evidencias/<nome>/resultado.json).

Uso, da raiz do repositório (precisa do Wireshark instalado, por causa do dumpcap e do tshark):
    python3 docs/relatorio/experimentos.py            # todos
    python3 docs/relatorio/experimentos.py q2 q3      # só alguns
"""

import datetime
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))

import integration_local as integ  # noqa: E402  (reaproveita a classe Roteador e as tabelas esperadas)

WIRESHARK = "/Applications/Wireshark.app/Contents/MacOS/"
DUMPCAP = shutil.which("dumpcap") or WIRESHARK + "dumpcap"
TSHARK = shutil.which("tshark") or WIRESHARK + "tshark"
CAPTURAS = os.path.join(AQUI, "capturas")
EVIDENCIAS = os.path.join(AQUI, "evidencias")
INTERFACE = "lo0"

LINHA_LOG = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \[([A-Z]+)\] (.*)$")


def end(n):
    return "10.6.%d.1" % n


def nome_curto(endereco):
    """'10.6.3.1' -> 'R3'."""
    return "R" + endereco.split(".")[2]


# ---------------------------------------------------------------------- rede de teste

class Rede:
    """Sobe a captura e os 5 roteadores; ao sair, encerra tudo e guarda os logs em evidencias/."""

    def __init__(self, nome, filtros=None, roteadores=(1, 2, 3, 4, 5)):
        self.nome = nome
        self.filtros = filtros or {}     # {n: regra do sobe_com_filtro.py}
        self.numeros = roteadores
        self.pasta = os.path.join(EVIDENCIAS, nome)
        self.captura = os.path.join(CAPTURAS, nome + ".pcapng")
        self.r = {}

    def comando(self, conf):
        n = int(os.path.basename(conf)[1])
        if n in self.filtros:
            return [sys.executable, "-u", os.path.join(AQUI, "sobe_com_filtro.py"), conf, self.filtros[n]]
        return [sys.executable, "-u", integ.ROUTER, conf]

    def subir(self, n):
        self.r[n] = integ.Roteador(n, self.pasta)

    def __enter__(self):
        shutil.rmtree(self.pasta, ignore_errors=True)
        os.makedirs(self.pasta)
        os.makedirs(CAPTURAS, exist_ok=True)
        if os.path.exists(self.captura):
            os.remove(self.captura)
        self.dumpcap = subprocess.Popen([DUMPCAP, "-q", "-i", INTERFACE, "-f", "udp portrange 6001-6005",
                                         "-w", self.captura],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if os.path.exists(self.captura):
                break
            time.sleep(0.1)
        time.sleep(1)
        integ.comando_roteador = self.comando
        for n in self.numeros:
            self.subir(n)
        self.partida = time.time()   # as renovações periódicas saem cerca de 30 s e 60 s depois daqui
        return self

    def __exit__(self, *erro):
        for roteador in self.r.values():
            if roteador.vivo():
                try:
                    roteador.proc.stdin.write("sair\n")
                    roteador.proc.stdin.flush()
                except OSError:
                    pass
        time.sleep(1)
        for roteador in self.r.values():
            if roteador.vivo():
                roteador.proc.kill()
        time.sleep(0.5)
        self.dumpcap.send_signal(signal.SIGINT)
        self.dumpcap.wait(timeout=10)
        os.chmod(self.captura, 0o644)
        for controle in ("arma_perda", "corta_enlace", "libera_lsp"):
            if os.path.exists(os.path.join(self.pasta, controle)):
                os.remove(os.path.join(self.pasta, controle))
        if os.path.isdir(os.path.join(self.pasta, "logs")):   # 'logs/' é ignorado pelo git
            os.rename(os.path.join(self.pasta, "logs"), os.path.join(self.pasta, "logs_roteadores"))

    def esperar_instante(self, segundos):
        """Espera até 'segundos' depois da partida dos roteadores."""
        time.sleep(max(0, self.partida + segundos - time.time()))

    def esperar_convergencia(self, limite=30):
        esperadas = {n: integ.como_tabela(integ.ESPERADA[n]) for n in self.numeros}
        ok = integ.esperar_ate(lambda: all(self.r[n].tabela() == esperadas[n] for n in self.numeros), limite)
        if not ok:
            raise RuntimeError("a rede nao convergiu")


def ler_log(rede, n):
    """[(instante em segundos, categoria, texto)] do log do roteador n."""
    linhas = []
    caminho = os.path.join(rede.pasta, "logs_roteadores", end(n) + ".log")
    with open(caminho, encoding="ascii") as arquivo:
        for linha in arquivo:
            m = LINHA_LOG.match(linha.rstrip("\n"))
            if m:
                instante = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp()
                linhas.append((instante, m.group(2), m.group(3)))
    return linhas


def texto_do_log_atual(rede, n):
    return rede.r[n].log()


def ler_captura(rede):
    """[{t, de, para, texto}] de todos os datagramas da captura (de/para = número do roteador)."""
    saida = subprocess.run([TSHARK, "-r", rede.captura, "-T", "fields", "-e", "frame.time_epoch",
                            "-e", "udp.srcport", "-e", "udp.dstport", "-e", "udp.payload"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
                           check=True).stdout
    pacotes = []
    for linha in saida.splitlines():
        partes = linha.split("\t")
        if len(partes) == 4 and partes[3]:
            pacotes.append({"t": float(partes[0]), "de": int(partes[1]) - 6000, "para": int(partes[2]) - 6000,
                            "texto": bytes.fromhex(partes[3]).decode("ascii", "replace")})
    return pacotes


def salvar(rede, resultado):
    resultado["captura"] = os.path.relpath(rede.captura, AQUI)   # no Q3, a da última rodada
    with open(os.path.join(rede.pasta, "resultado.json"), "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, indent=2, ensure_ascii=False)
    print(json.dumps(resultado, indent=1, ensure_ascii=False)[:3500], flush=True)


def esperar_no_log(rede, n, trecho, limite=40):
    """Espera aparecer 'trecho' no log do roteador n. Devolve True se apareceu."""
    return integ.esperar_ate(lambda: trecho in texto_do_log_atual(rede, n), limite)


# ---------------------------------------------------------------------- Q1: Dijkstra

def ler_lsdb(linhas):
    """Linhas do comando lsdb -> {origem: (seq, {vizinho: custo})}."""
    lsdb = {}
    for linha in linhas:
        partes = linha.split(None, 2)
        if len(partes) == 3 and partes[0].startswith("10.") and partes[1].isdigit():
            vizinhos = {}
            for item in partes[2].split(","):
                vizinho, custo = item.strip().split("=")
                vizinhos[vizinho] = int(custo)
            lsdb[partes[0]] = (int(partes[1]), vizinhos)
    return lsdb


def dijkstra_passo_a_passo(grafo, origem):
    """Tabela de iterações como na aula: a cada passo, N' e D(v),p(v) de cada nó."""
    nos = sorted(grafo)
    custo = {origem: 0}
    anterior = {}
    finalizados = []
    iteracoes = []
    while True:
        candidatos = [n for n in nos if n in custo and n not in finalizados]
        if not candidatos:
            break
        u = min(candidatos, key=lambda n: (custo[n], n))
        finalizados.append(u)
        for v, c in grafo.get(u, {}).items():
            if v not in finalizados and (v not in custo or custo[u] + c < custo[v]):
                custo[v] = custo[u] + c
                anterior[v] = u
        iteracoes.append({"passo": len(iteracoes), "escolhido": nome_curto(u),
                          "N": [nome_curto(n) for n in finalizados],
                          "D": {nome_curto(v): ("inf" if v not in custo else
                                                "%d,%s" % (custo[v], nome_curto(anterior[v])))
                                for v in nos if v != origem}})
    rotas = {}
    for v in nos:
        if v != origem and v in custo:
            salto = v
            while anterior[salto] != origem:
                salto = anterior[salto]
            rotas["10.6.%s.0/24" % v.split(".")[2]] = [salto, custo[v]]
    return iteracoes, rotas


def q1():
    print("\n===== Q1: Dijkstra", flush=True)
    with Rede("q1_dijkstra") as rede:
        rede.esperar_convergencia()
        time.sleep(1)
        linhas_lsdb = rede.r[1].comando("lsdb")
        linhas_tabela = rede.r[1].comando("tabela")
        linhas_vizinhos = rede.r[1].comando("vizinhos")
        tabela = rede.r[1].tabela()
        todas = {("R%d" % n): rede.r[n].comando("tabela") for n in rede.numeros}
    lsdb = ler_lsdb(linhas_lsdb)
    grafo = {origem: viz for origem, (_, viz) in lsdb.items()}
    iteracoes, rotas = dijkstra_passo_a_passo(grafo, end(1))
    programa = {rede_d: [prox, c] for rede_d, (prox, c) in tabela.items()}
    salvar(rede, {"lsdb_r1": linhas_lsdb, "tabela_r1": linhas_tabela, "vizinhos_r1": linhas_vizinhos,
                  "tabelas": todas, "iteracoes": iteracoes, "rotas_a_mao": rotas,
                  "igual_ao_programa": rotas == programa})


# ---------------------------------------------------------------------- Q2: inundação

ENLACES = {(1, 2): 1, (1, 3): 4, (2, 3): 2, (2, 4): 7, (3, 5): 3, (4, 5): 5}


def vetor_distancia(caiu, poison=False, infinito=16):
    """Modelo simples de vetor de distância em rodadas síncronas, com atualização disparada.

    A cada rodada, quem mudou envia seu vetor inteiro a cada vizinho vivo. Devolve quantas mensagens
    e rodadas são gastas, a partir da queda do roteador 'caiu', até a rede estabilizar.
    """
    custo = {}
    for (a, b), c in ENLACES.items():
        custo.setdefault(a, {})[b] = c
        custo.setdefault(b, {})[a] = c
    nos = sorted(custo)
    destinos = list(nos)     # o roteador que cai continua sendo destino, até virar infinito
    recebido = {n: {v: {} for v in custo[n]} for n in nos}

    def calcular(n):
        vetor, proximo = {n: 0}, {n: n}
        for d in destinos:
            if d == n:
                continue
            melhor, salto = infinito, None
            for v in sorted(recebido[n]):
                total = custo[n][v] + recebido[n][v].get(d, infinito)
                if total < melhor:
                    melhor, salto = total, v
            vetor[d], proximo[d] = melhor, salto
        return vetor, proximo

    def anuncio(n, para, vetor, proximo):
        if not poison:
            return dict(vetor)
        return {d: (infinito if proximo.get(d) == para and d != n else c) for d, c in vetor.items()}

    # 1. converge antes da queda
    estado = {n: ({d: (0 if d == n else infinito) for d in destinos}, {n: n}) for n in nos}
    mudou = set(nos)
    while mudou:
        for s in mudou:
            for v in custo[s]:
                recebido[v][s] = anuncio(s, v, *estado[s])
        novo = {n: calcular(n) for n in nos}
        mudou = {n for n in nos if novo[n][0] != estado[n][0]}
        estado = novo

    # 2. queda: os vizinhos perdem o enlace e recalculam
    for n in custo[caiu]:
        del recebido[n][caiu]
        del custo[n][caiu]
    del custo[caiu]
    nos = [n for n in nos if n != caiu]
    mensagens = rodadas = 0
    novo = {n: calcular(n) for n in nos}
    mudou = {n for n in nos if novo[n][0] != estado[n][0]}
    estado = novo
    while mudou:
        rodadas += 1
        for s in mudou:
            for v in custo[s]:
                recebido[v][s] = anuncio(s, v, *estado[s])
                mensagens += 1
        novo = {n: calcular(n) for n in nos}
        mudou = {n for n in nos if novo[n][0] != estado[n][0]}
        estado = novo
    return {"mensagens": mensagens, "rodadas": rodadas, "infinito": infinito, "poison_reverse": poison}


# Quedas entre 31 e 36 s após a partida: a detecção (15 a 20,5 s depois) fica entre as renovações
# de 30 s e 60 s, e a captura mostra só o efeito de UMA mudança (D52).
INSTANTES_Q2 = (31, 32.25, 33.5, 34.75, 36)
ATRASOS_Q3 = (0.3, 1.4, 2.5, 3.6, 4.7)   # somados aos 31 s; variam a fase em relação ao HELLO


def renovacoes_entre(rede, inicio, fim, roteadores):
    """Quantas renovações periódicas os logs registram no intervalo."""
    return sum(1 for n in roteadores for t, cat, texto in ler_log(rede, n)
               if cat == "LSP" and "renovacao periodica" in texto and inicio <= t <= fim)


def uma_queda_do_r4(nome, instante):
    """Derruba o R4 no instante dado e conta, na captura e nos logs, os LSPs gerados pela queda."""
    with Rede(nome) as rede:
        rede.esperar_convergencia()
        rede.esperar_instante(instante)
        instante_queda = time.time()
        rede.r[4].proc.kill()
        for n in (2, 5):
            esperar_no_log(rede, n, "10.6.4.1 (127.0.0.1:6004) ficou INATIVO")
        time.sleep(1)
    gerados = {}
    for n in (2, 5):
        for t, cat, texto in ler_log(rede, n):
            m = re.match(r"LSP proprio gerado \(vizinho 10\.6\.4\.1 ficou inativo\): seq (\d+)", texto)
            if cat == "LSP" and m:
                gerados[(end(n), int(m.group(1)))] = t
    pacotes = []
    outros = []     # LSPs que não são da queda (renovações), para confirmar que a janela está limpa
    for p in ler_captura(rede):
        if p["texto"].startswith("LSP:"):
            campos = p["texto"].split(":")
            if (campos[1], int(campos[2])) in gerados:
                pacotes.append(dict(p, origem=campos[1], seq=int(campos[2])))
            else:
                outros.append(p)
    fim_janela = max(p["t"] for p in pacotes) + 0.5
    extras = sum(1 for p in outros if instante_queda <= p["t"] <= fim_janela)
    renovacoes = renovacoes_entre(rede, instante_queda, fim_janela, (1, 2, 3, 5))
    if extras or renovacoes:
        raise RuntimeError("%s: a janela da queda tem %d LSPs extras e %d renovacoes" % (nome, extras, renovacoes))
    por_lsp = {}
    for (origem, seq) in gerados:
        desse = [p for p in pacotes if p["origem"] == origem and p["seq"] == seq]
        novos = copias = antigos = propria = 0
        for n in (1, 2, 3, 5):
            for _, cat, texto in ler_log(rede, n):
                if cat != "LSP":
                    continue
                if texto.startswith("LSP novo: %s seq %d " % (origem, seq)):
                    novos += 1
                elif texto.startswith("LSP descartado (copia/antigo): %s seq %d (LSDB tem seq %d)" % (origem, seq, seq)):
                    copias += 1     # mesma sequência: cópia idêntica
                elif texto.startswith("LSP descartado (copia/antigo): %s seq %d " % (origem, seq)):
                    antigos += 1    # a LSDB já tinha um LSP mais novo dessa origem
                elif n == int(origem.split(".")[2]) and texto.startswith("LSP descartado (propria origem): seq %d," % seq):
                    propria += 1
        ao_morto = sum(1 for p in desse if p["para"] == 4)
        por_lsp[nome_curto(origem)] = {
            "seq": seq, "transmissoes": len(desse), "aceitos_como_novos": novos,
            "descartados_copia": copias, "descartados_antigos": antigos, "descartados_propria_origem": propria,
            "enviados_ao_R4_morto": ao_morto,
            "fecha_a_conta": len(desse) == novos + copias + antigos + propria + ao_morto,
            "duracao_na_captura_ms": round((max(p["t"] for p in desse) - min(p["t"] for p in desse)) * 1000, 3),
            "caminho": ["R%d->R%d" % (p["de"], p["para"]) for p in sorted(desse, key=lambda x: x["t"])]}
    total = {c: sum(d[c] for d in por_lsp.values())
             for c in ("transmissoes", "aceitos_como_novos", "descartados_copia", "descartados_antigos",
                       "descartados_propria_origem", "enviados_ao_R4_morto")}
    inicio = min(gerados.values())
    filtro = " or ".join('udp contains "LSP:%s:%d"' % par for par in sorted(gerados))
    return rede, {"queda": "R4", "queda_apos_a_partida_s": round(instante_queda - rede.partida, 2),
                  "lsps_gerados_pela_mudanca": len(gerados), "por_lsp": por_lsp, "total": total,
                  "lsps_extras_na_janela": extras, "renovacoes_na_janela": renovacoes, "filtro": filtro,
                  "segundos_entre_queda_e_primeiro_lsp": round(inicio - instante_queda, 3)}


def resumo_da_rodada(k, resultado, captura):
    return dict(resultado["total"], rodada=k, captura=captura, filtro=resultado["filtro"],
                queda_apos_a_partida_s=resultado["queda_apos_a_partida_s"],
                lsps_extras_na_janela=resultado["lsps_extras_na_janela"])


def q2():
    print("\n===== Q2: inundacao (queda do R4, %d rodadas)" % len(INSTANTES_Q2), flush=True)
    rede, principal = uma_queda_do_r4("q2_inundacao", INSTANTES_Q2[0])
    rodadas = [resumo_da_rodada(1, principal, "capturas/q2_inundacao.pcapng")]
    for k, instante in enumerate(INSTANTES_Q2[1:], start=2):
        outra, resultado = uma_queda_do_r4("q2_repeticao_%d" % k, instante)
        salvar(outra, resultado)
        rodadas.append(resumo_da_rodada(k, resultado, "capturas/q2_repeticao_%d.pcapng" % k))
    principal["rodadas"] = rodadas
    principal["vetor_distancia"] = [vetor_distancia(4), vetor_distancia(4, infinito=64),
                                    vetor_distancia(4, poison=True), vetor_distancia(4, poison=True, infinito=64)]
    salvar(rede, principal)


# ---------------------------------------------------------------------- Q3: convergência

def tempo_dijkstra(repeticoes=20000):
    """Tempo médio, em microssegundos, de uma execução do dijkstra.py real sobre a local5."""
    import dijkstra
    grafo = {}
    for (a, b), c in ENLACES.items():
        grafo.setdefault(end(a), {})[end(b)] = c
        grafo.setdefault(end(b), {})[end(a)] = c
    inicio = time.perf_counter()
    for _ in range(repeticoes):
        dijkstra.dijkstra(grafo, end(1))
    return (time.perf_counter() - inicio) / repeticoes * 1e6


def q3(rodadas=5):
    print("\n===== Q3: convergencia (queda do R2, %d rodadas)" % rodadas, flush=True)
    medidas = []
    for k in range(rodadas):
        with Rede("q3_convergencia_%d" % (k + 1)) as rede:
            rede.esperar_convergencia()
            rede.esperar_instante(31 + ATRASOS_Q3[k % 5])   # D52: longe das renovações de 30 e 60 s
            queda = time.time()
            rede.r[2].proc.kill()
            esperadas = {n: integ.como_tabela(integ.SEM_R2[n]) for n in (1, 3, 4, 5)}
            ok = integ.esperar_ate(lambda: all(rede.r[n].tabela() == esperadas[n] for n in (1, 3, 4, 5)), 35)
            time.sleep(1)
        capturados = ler_captura(rede)
        # Instante real do último HELLO do R2, medido no pacote (o log é gravado logo depois do envio)
        ultimo_hello = max(p["t"] for p in capturados if p["de"] == 2 and p["texto"].startswith("HELLO") and p["t"] <= queda)
        deteccoes = {}
        for n in (1, 3, 4):
            deteccoes[n] = min(t for t, cat, txt in ler_log(rede, n)
                               if cat == "VIZINHO" and "10.6.2.1" in txt and "INATIVO" in txt)
        primeira = min(deteccoes.values())
        mudancas = [t for n in (1, 3, 4, 5) for t, cat, txt in ler_log(rede, n)
                    if cat == "TABELA" and "MUDOU" in txt and t >= queda]
        rota_r1_r3 = min(t for t, cat, txt in ler_log(rede, 1)
                         if cat == "TABELA" and t >= queda and "10.6.3.0/24 via 10.6.3.1 (custo 4)" in txt)
        ultima = max(mudancas)
        renovacoes = renovacoes_entre(rede, queda, ultima + 0.5, (1, 3, 4, 5))
        if renovacoes:
            raise RuntimeError("Q3 rodada %d: %d renovacoes na janela da queda" % (k + 1, renovacoes))
        gerados = set()
        for n in (1, 3, 4):
            for _, cat, txt in ler_log(rede, n):
                m = re.match(r"LSP proprio gerado \(vizinho 10\.6\.2\.1 ficou inativo\): seq (\d+)", txt)
                if cat == "LSP" and m:
                    gerados.add((end(n), m.group(1)))
        instantes = {}
        for p in capturados:
            campos = p["texto"].split(":")
            if campos[0] == "LSP" and (campos[1], campos[2]) in gerados and p["para"] != 2:
                instantes.setdefault((campos[1], campos[2]), []).append(p["t"])
        inundacao = max(max(v) - min(v) for v in instantes.values()) * 1000
        medidas.append({"rodada": k + 1, "tabelas_finais_corretas": ok,
                        "queda_apos_a_partida_s": round(queda - rede.partida, 2), "renovacoes_na_janela": renovacoes,
                        "queda_apos_ultimo_hello_s": round(queda - ultimo_hello, 3),
                        "deteccao_s": round(primeira - queda, 3),
                        "primeira_deteccao_apos_ultimo_hello_s": round(primeira - ultimo_hello, 3),
                        "diferenca_entre_detectores_ms": round((max(deteccoes.values()) - primeira) * 1000, 1),
                        "inundacao_e_recalculo_ms": round((ultima - primeira) * 1000, 1),
                        "maior_inundacao_de_um_lsp_ms": round(inundacao, 3),
                        "rota_r1_r3_apos_queda_s": round(rota_r1_r3 - queda, 3),
                        "total_s": round(ultima - queda, 3)})
    def resumo(campo):
        valores = [m[campo] for m in medidas]
        return {"min": min(valores), "media": round(sum(valores) / len(valores), 3), "max": max(valores)}
    rede.pasta = os.path.join(EVIDENCIAS, "q3_resumo")
    os.makedirs(rede.pasta, exist_ok=True)
    salvar(rede, {"queda": "R2 (caminho R1-R2-R3)", "medidas": medidas,
                  "resumo": {c: resumo(c) for c in ("deteccao_s", "primeira_deteccao_apos_ultimo_hello_s",
                                                    "diferenca_entre_detectores_ms", "inundacao_e_recalculo_ms",
                                                    "maior_inundacao_de_um_lsp_ms", "total_s")},
                  "um_dijkstra_na_local5_us": round(tempo_dijkstra(), 1)})


# ---------------------------------------------------------------------- Q4: número de sequência

def q4():
    print("\n===== Q4: numero de sequencia", flush=True)
    with Rede("q4_sequencia") as rede:
        rede.esperar_convergencia()
        time.sleep(1)

        # Parte 1: reinício REAL do R2, com o LSP antigo dele ainda guardado na LSDB do R1
        seq_antigo = rede.r[1].lsdb()[end(2)]
        rede.r[2].proc.kill()
        time.sleep(2)
        ainda_na_lsdb = rede.r[1].lsdb().get(end(2))
        rede.subir(2)
        aceito = integ.esperar_ate(lambda: rede.r[1].lsdb().get(end(2), 0) > seq_antigo, 15)
        seq_reinicio = min(int(m) for m in re.findall(r"LSP novo: 10\.6\.2\.1 seq (\d+) ", texto_do_log_atual(rede, 1))
                           if int(m) > seq_antigo)
        log_reinicio = [l for l in texto_do_log_atual(rede, 1).splitlines()
                        if "LSP novo: 10.6.2.1 seq %d " % seq_reinicio in l]
        integ.esperar_ate(lambda: all(rede.r[n].tabela() == integ.como_tabela(integ.ESPERADA[n])
                                      for n in rede.numeros), 20)
        time.sleep(1)

        # Parte 2: um R2 que recomeçasse do 0, usando o mesmo par (IP, porta) do R2 verdadeiro
        seq_guardado = rede.r[1].lsdb()[end(2)]
        rede.r[2].proc.kill()
        time.sleep(0.5)
        falso = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        falso.bind(("127.0.0.1", 6002))
        for seq in (0, 1, 2):
            falso.sendto(b"LSP:10.6.2.1:%d:10.6.1.1=1;10.6.3.1=2" % seq, ("127.0.0.1", 6001))
            time.sleep(0.3)
        time.sleep(0.7)
        depois_dos_baixos = rede.r[1].lsdb()[end(2)]
        log_baixos = [l for l in texto_do_log_atual(rede, 1).splitlines()
                      if re.search(r"copia/antigo\): 10\.6\.2\.1 seq [012] ", l)]

        # Só depois de 90 s sem renovação o LSP antigo sai da LSDB e um seq baixo volta a ser aceito
        esperar_no_log(rede, 1, "LSP de 10.6.2.1 envelhecido", 100)
        time.sleep(0.5)
        falso.sendto(b"LSP:10.6.2.1:3:10.6.1.1=1;10.6.3.1=2", ("127.0.0.1", 6001))
        time.sleep(1)
        falso.close()
        depois_de_envelhecer = rede.r[1].lsdb().get(end(2))
        log_envelheceu = [l for l in texto_do_log_atual(rede, 1).splitlines()
                          if "LSP de 10.6.2.1 envelhecido" in l or "LSP novo: 10.6.2.1 seq 3 " in l]
    salvar(rede, {"seq_antigo_na_lsdb_do_r1": seq_antigo, "lsp_antigo_ainda_na_lsdb_ao_reiniciar": ainda_na_lsdb == seq_antigo,
                  "seq_apos_reinicio_real": seq_reinicio, "reinicio_real_aceito": aceito and seq_reinicio > seq_antigo,
                  "log_do_r1_sobre_o_reinicio": log_reinicio, "seq_guardado_antes_dos_lsps_baixos": seq_guardado,
                  "seq_na_lsdb_depois_dos_lsps_baixos": depois_dos_baixos,
                  "lsps_baixos_descartados": depois_dos_baixos == seq_guardado and len(log_baixos) == 3,
                  "log_do_r1_sobre_os_seq_baixos": log_baixos, "log_do_r1_apos_90s": log_envelheceu,
                  "seq_baixo_aceito_apos_envelhecer": depois_de_envelhecer == 3})


# ---------------------------------------------------------------------- Q5: LSP perdido

def q5():
    print("\n===== Q5: LSP perdido", flush=True)
    with Rede("q5_confiabilidade", filtros={1: "q5"}) as rede:
        rede.esperar_convergencia()
        time.sleep(1)
        open(os.path.join(rede.pasta, "arma_perda"), "w").close()
        rede.r[4].proc.kill()
        queda = time.time()
        perda = os.path.join(rede.pasta, "falhas_injetadas.txt")
        integ.esperar_ate(lambda: os.path.exists(perda), 30)
        time.sleep(1)
        with open(perda, encoding="ascii") as arquivo:
            instante_perda = float(arquivo.readline().split()[0])
        tabela_r1 = rede.r[1].comando("tabela")
        lsdb_r1 = rede.r[1].comando("lsdb")
        tabela_r3 = rede.r[3].comando("tabela")
        ping = rede.r[1].comando("ping 10.6.4.1", 2.4)
        recuperou = integ.esperar_ate(lambda: "10.6.4.0/24" not in rede.r[1].tabela(), 35)
        instante_recuperacao = time.time()
        tabela_depois = rede.r[1].comando("tabela")
        lsdb_depois = rede.r[1].comando("lsdb")
    with open(perda, encoding="ascii") as arquivo:
        perdidos = [l.strip() for l in arquivo]
    novos_r5 = [(t, txt) for t, cat, txt in ler_log(rede, 1) if cat == "LSP" and txt.startswith("LSP novo: 10.6.5.1")
                and t > instante_perda]
    renovacao_r5 = [txt for t, cat, txt in ler_log(rede, 5) if cat == "LSP" and "renovacao periodica" in txt
                    and t > instante_perda]
    recebido = novos_r5[0][0] if novos_r5 else None
    salvar(rede, {"queda": "R4", "copias_perdidas_pelo_r1": perdidos,
                  "tabela_r1_com_lsdb_desatualizada": tabela_r1, "lsdb_r1_desatualizada": lsdb_r1,
                  "tabela_r3_no_mesmo_momento": tabela_r3, "ping_r1_para_r4_nesse_momento": ping,
                  "recuperou": recuperou, "tabela_r1_depois": tabela_depois, "lsdb_r1_depois": lsdb_depois,
                  "lsp_que_recuperou": novos_r5[0][1] if novos_r5 else None,
                  "renovacao_do_r5": renovacao_r5[:1],
                  "segundos_com_lsdb_desatualizada": round(recebido - instante_perda, 3) if recebido else None,
                  "segundos_desde_a_queda_ate_notar": round(instante_recuperacao - queda, 1)})


# ---------------------------------------------------------------------- Q6: laço durante a convergência

def q6():
    print("\n===== Q6: laco durante a convergencia", flush=True)
    filtros = {1: "q6_corte:6002", 2: "q6_corte:6001", 3: "q6_atraso"}
    with Rede("q6_ttl_laco", filtros=filtros) as rede:
        rede.esperar_convergencia()
        time.sleep(1)
        antes = {"R2": rede.r[2].comando("tabela"), "R3": rede.r[3].comando("tabela")}
        open(os.path.join(rede.pasta, "corta_enlace"), "w").close()   # corta o enlace R1-R2
        esperar_no_log(rede, 2, "10.6.1.1 (127.0.0.1:6001) ficou INATIVO")
        esperar_no_log(rede, 1, "10.6.2.1 (127.0.0.1:6002) ficou INATIVO")
        time.sleep(1)
        durante = {"R2": rede.r[2].comando("tabela"), "R3": rede.r[3].comando("tabela")}
        inicio_ping = time.time()
        ping_laco = rede.r[5].comando("ping 10.6.1.1", 2.4)
        fim_ping = time.time()
        open(os.path.join(rede.pasta, "libera_lsp"), "w").close()     # o LSP atrasado volta a passar
        convergiu = integ.esperar_ate(lambda: rede.r[3].tabela().get("10.6.1.0/24") == (end(1), 4), 35)
        time.sleep(1)
        depois = {"R2": rede.r[2].comando("tabela"), "R3": rede.r[3].comando("tabela")}
        ping_depois = rede.r[5].comando("ping 10.6.1.1", 2.4)
    saltos = []
    for p in ler_captura(rede):
        if p["texto"].startswith("ICMP:") and inicio_ping - 0.1 <= p["t"] <= fim_ping:
            campos = p["texto"].split(":")
            saltos.append({"enlace": "R%d->R%d" % (p["de"], p["para"]), "tipo": int(campos[5]),
                           "ttl": int(campos[3]), "pacote": p["texto"]})
    ida = [s for s in saltos if s["tipo"] == 8]
    salvar(rede, {"enlace_cortado": "R1-R2", "tabelas_antes": antes, "tabelas_durante_o_laco": durante,
                  "ping_r5_para_r1_durante": ping_laco, "saltos_do_pedido": ida,
                  "demais_pacotes_icmp": [s for s in saltos if s["tipo"] != 8],
                  "convergiu_depois": convergiu, "tabelas_depois": depois, "ping_r5_para_r1_depois": ping_depois})


EXPERIMENTOS = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5, "q6": q6}

if __name__ == "__main__":
    for nome in (sys.argv[1:] or sorted(EXPERIMENTOS)):
        EXPERIMENTOS[nome]()
    print("\nFIM dos experimentos", flush=True)
