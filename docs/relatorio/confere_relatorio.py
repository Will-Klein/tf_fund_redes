"""Auditoria do relatório: recalcula os números a partir das FONTES BRUTAS e compara com o PDF.

Fontes usadas aqui: as capturas .pcapng (lidas com tshark), os logs dos roteadores, os arquivos de
configuração e as constantes do código. Os valores em resultado.json só são usados para comparar.
Não importa experimentos.py nem gera_relatorio.py: é uma segunda conta, feita de outro jeito.

Uso, da raiz do repositório: python3 docs/relatorio/confere_relatorio.py
Termina com código 1 se alguma verificação falhar.
"""

import datetime
import glob
import itertools
import json
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, RAIZ)

import forwarding  # noqa: E402
import router      # noqa: E402

TSHARK = shutil.which("tshark") or "/Applications/Wireshark.app/Contents/MacOS/tshark"
LINHA = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \[([A-Z]+)\] (.*)$")
resultados = []


def conferir(descricao, ok, detalhe=""):
    resultados.append(bool(ok))
    print("[%s] %s%s" % ("OK" if ok else "FALHOU", descricao, "" if ok else "  -> %s" % (detalhe,)), flush=True)


def perto(a, b, tolerancia):
    return abs(a - b) <= tolerancia


def end(n):
    return "10.6.%d.1" % n


def json_de(nome):
    with open(os.path.join(AQUI, "evidencias", nome, "resultado.json"), encoding="utf-8") as arquivo:
        return json.load(arquivo)


def pacotes(nome):
    """Todos os datagramas da captura: {q, t, de, para, txt}."""
    saida = subprocess.run([TSHARK, "-r", os.path.join(AQUI, "capturas", nome + ".pcapng"), "-T", "fields",
                            "-e", "frame.number", "-e", "frame.time_epoch", "-e", "udp.srcport", "-e", "udp.dstport",
                            "-e", "udp.payload"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           universal_newlines=True, check=True).stdout
    lista = []
    for linha in saida.splitlines():
        p = linha.split("\t")
        if len(p) == 5 and p[4]:
            lista.append({"q": int(p[0]), "t": float(p[1]), "de": int(p[2]) - 6000, "para": int(p[3]) - 6000,
                          "txt": bytes.fromhex(p[4]).decode("ascii", "replace")})
    return lista


def log(nome, n):
    """[(t, categoria, texto)] do log do roteador n."""
    linhas = []
    with open(os.path.join(AQUI, "evidencias", nome, "logs_roteadores", end(n) + ".log"), encoding="ascii") as arquivo:
        for linha in arquivo:
            m = LINHA.match(linha.rstrip("\n"))
            if m:
                t = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp()
                linhas.append((t, m.group(2), m.group(3)))
    return linhas


def enlaces_das_configs():
    enlaces = {}
    for caminho in sorted(glob.glob(os.path.join(RAIZ, "configs", "local5", "r*.conf"))):
        n = int(os.path.basename(caminho)[1])
        with open(caminho, encoding="utf-8") as arquivo:
            for linha in arquivo:
                partes = linha.split("#")[0].split()
                if partes and partes[0] == "vizinho":
                    enlaces[(n, int(partes[2]) - 6000)] = int(partes[3])
    return enlaces


# ---------------------------------------------------------------------- base

def base():
    print("\n== Base: código, configuração e capturas")
    conferir("temporizadores do código = enunciado (5, 20, 30, 90 s)",
             (router.HELLO_INTERVAL, router.NEIGHBOR_TIMEOUT, router.LSP_REFRESH, router.LSP_MAX_AGE) == (5, 20, 30, 90))
    conferir("TTL inicial 16 e timeout do ping 2 s", (forwarding.TTL_INICIAL, forwarding.PING_TIMEOUT) == (16, 2.0))
    e = enlaces_das_configs()
    unicos = {tuple(sorted(k)): v for k, v in e.items()}
    conferir("local5: 5 roteadores e 6 enlaces", len({a for a, _ in e}) == 5 and len(unicos) == 6)
    conferir("local5: custos iguais nos dois lados", all(e[(b, a)] == c for (a, b), c in e.items()))
    conferir("local5: todos os custos diferentes", len(set(unicos.values())) == 6)
    capturas = sorted(glob.glob(os.path.join(AQUI, "capturas", "*.pcapng")))
    esperadas = ["q1_dijkstra", "q2_inundacao"] + ["q2_repeticao_%d" % k for k in range(2, 6)] + \
                ["q3_convergencia_%d" % k for k in range(1, 6)] + ["q4_sequencia", "q5_confiabilidade", "q6_ttl_laco"]
    conferir("as 14 capturas citadas existem", sorted(os.path.basename(c)[:-7] for c in capturas) == sorted(esperadas))
    for nome in esperadas:
        lista = pacotes(nome)
        tipos = {p["txt"].split(":")[0] for p in lista}
        if not (lista and tipos <= {"HELLO", "LSP", "DADOS", "ICMP"}):
            conferir("captura %s só tem pacotes do trabalho" % nome, False, tipos)
    conferir("todas as capturas têm só pacotes HELLO/LSP/DADOS/ICMP", all(resultados))
    ip = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    formatos = {"HELLO": r"HELLO:%s" % ip, "LSP": r"LSP:%s:\d+:(%s=\d+(;%s=\d+)*)?" % (ip, ip, ip),
                "DADOS": r"DADOS:%s:%s:\d+:\d+:[^:]*" % (ip, ip), "ICMP": r"ICMP:%s:%s:\d+:\d+:(0|3|8|11)" % (ip, ip)}
    fora = [p["txt"] for nome in esperadas for p in pacotes(nome)
            if not re.fullmatch(formatos[p["txt"].split(":")[0]], p["txt"])]
    conferir("todo pacote das capturas segue o formato literal do enunciado", not fora, fora[:3])
    enderecos, portas = set(), set()
    for nome in esperadas:
        saida = subprocess.run([TSHARK, "-r", os.path.join(AQUI, "capturas", nome + ".pcapng"), "-T", "fields", "-e", "ip.src",
                                "-e", "ip.dst", "-e", "udp.srcport", "-e", "udp.dstport"], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, universal_newlines=True, check=True).stdout
        for linha in saida.splitlines():
            ip_o, ip_d, porta_o, porta_d = linha.split("\t")
            enderecos |= {ip_o, ip_d}
            portas |= {int(porta_o), int(porta_d)}
    conferir("todos os pacotes são 127.0.0.1, nas portas 6001 a 6005",
             enderecos == {"127.0.0.1"} and portas == set(range(6001, 6006)), (enderecos, portas))


# ---------------------------------------------------------------------- Q1

def q1():
    print("\n== Q1: Dijkstra")
    r = json_de("q1_dijkstra")
    grafo, seqs = {}, {}
    for linha in r["lsdb_r1"][1:]:
        o, seq, viz = linha.split(None, 2)
        seqs[o] = int(seq)
        grafo[o] = {x.split("=")[0].strip(): int(x.split("=")[1]) for x in viz.split(",")}
    # A LSDB mostrada precisa ser o último LSP de cada origem que aparece na captura
    ultimo = {}
    for p in pacotes("q1_dijkstra"):
        if p["txt"].startswith("LSP:"):
            _, o, seq, lista = p["txt"].split(":")
            if o not in ultimo or int(seq) > ultimo[o][0]:
                ultimo[o] = (int(seq), {x.split("=")[0]: int(x.split("=")[1]) for x in lista.split(";") if x})
    conferir("LSDB do relatório = último LSP de cada origem na captura",
             all(ultimo[o] == (seqs[o], grafo[o]) for o in grafo), ultimo)
    e = enlaces_das_configs()
    conferir("LSDB do relatório = arestas das configs",
             {(int(a.split(".")[2]), int(b.split(".")[2])): c for a in grafo for b, c in grafo[a].items()} == e)
    # Tabela 1, refeita
    custo, ant, feitos = {end(1): 0}, {}, []
    certo = True
    for it in r["iteracoes"]:
        u = min((x for x in custo if x not in feitos), key=lambda x: custo[x])
        feitos.append(u)
        for v, c in grafo[u].items():
            if v not in feitos and custo[u] + c < custo.get(v, 10 ** 9):
                custo[v], ant[v] = custo[u] + c, u
        linha = {"R%d" % k: ("%d,R%s" % (custo[end(k)], ant[end(k)].split(".")[2]) if end(k) in custo else "inf")
                 for k in range(2, 6)}
        certo = certo and linha == it["D"] and it["N"] == ["R" + x.split(".")[2] for x in feitos]
    conferir("Tabela 1 (iterações) refeita passo a passo", certo and len(r["iteracoes"]) == 5)
    # Tabela do programa para TODOS os roteadores contra todos os caminhos possíveis
    falhas = 0
    for k in range(1, 6):
        origem = end(k)
        tabela = {l.split()[0]: (l.split()[1], int(l.split()[2])) for l in r["tabelas"]["R%d" % k][1:]}
        for d in grafo:
            if d == origem:
                continue
            caminhos = []
            meio = [x for x in grafo if x not in (origem, d)]
            for t in range(len(meio) + 1):
                for trecho in itertools.permutations(meio, t):
                    c = [origem] + list(trecho) + [d]
                    if all(c[i + 1] in grafo[c[i]] for i in range(len(c) - 1)):
                        caminhos.append((sum(grafo[c[i]][c[i + 1]] for i in range(len(c) - 1)), c[1]))
            menor = min(x for x, _ in caminhos)
            melhores = [s for x, s in caminhos if x == menor]
            if len(melhores) != 1 or tabela["10.6.%s.0/24" % d.split(".")[2]] != (melhores[0], menor):
                falhas += 1
    conferir("as 20 rotas do programa = menor caminho entre todos os possíveis, sem empate", falhas == 0, falhas)


# ---------------------------------------------------------------------- Q2

def contar_q2(nome):
    gerados = set()
    for n in (2, 5):
        for _, cat, txt in log(nome, n):
            m = re.match(r"LSP proprio gerado \(vizinho 10\.6\.4\.1 ficou inativo\): seq (\d+)", txt)
            if cat == "LSP" and m:
                gerados.add((end(n), m.group(1)))
    outros_motivos = [txt for n in (1, 3) for _, cat, txt in log(nome, n) if "LSP proprio gerado (vizinho 10.6.4.1" in txt]
    todos = pacotes(nome)
    lista = [p for p in todos if p["txt"].startswith("LSP:") and tuple(p["txt"].split(":")[1:3]) in gerados]
    # Janela da mudança: da queda do R4 (primeiro LSP gerado menos o atraso medido) até logo depois do último LSP
    primeiro = min(t for n in (2, 5) for t, cat, txt in log(nome, n) if "LSP proprio gerado (vizinho 10.6.4.1 ficou inativo" in txt)
    inicio = primeiro - json_de(nome)["segundos_entre_queda_e_primeiro_lsp"]
    fim = max(p["t"] for p in lista) + 0.5
    extras = sum(1 for p in todos if p["txt"].startswith("LSP:") and inicio <= p["t"] <= fim
                 and tuple(p["txt"].split(":")[1:3]) not in gerados)
    aceitos = copias = antigos = renovacoes = 0
    for n in (1, 2, 3, 5):
        for t, cat, txt in log(nome, n):
            renovacoes += "renovacao periodica" in txt and inicio <= t <= fim
            for o, s in gerados:
                aceitos += txt.startswith("LSP novo: %s seq %s " % (o, s))
                if txt.startswith("LSP descartado (copia/antigo): %s seq %s " % (o, s)):
                    if txt.startswith("LSP descartado (copia/antigo): %s seq %s (LSDB tem seq %s)" % (o, s, s)):
                        copias += 1
                    else:
                        antigos += 1
    return {"gerados": len(gerados), "transmissoes": len(lista), "aceitos": aceitos, "copias": copias, "antigos": antigos,
            "ao_r4": sum(p["para"] == 4 for p in lista), "outros": len(outros_motivos), "extras": extras,
            "renovacoes": renovacoes}


def dv_independente(caiu, poison, inf):
    """Mesmo modelo do relatório, escrito de outro jeito: parte dos menores caminhos já calculados."""
    viz = {}
    for (a, b), c in enlaces_das_configs().items():
        viz.setdefault(a, {})[b] = c
    todos = sorted(viz)
    dist = {a: {b: (0 if a == b else inf) for b in todos} for a in todos}
    for _ in todos:
        for a in todos:
            for b in todos:
                for v, c in viz[a].items():
                    if a != b:
                        dist[a][b] = min(dist[a][b], c + dist[v][b])
    prox = {a: {b: min(viz[a], key=lambda v: viz[a][v] + dist[v][b]) for b in todos if b != a} for a in todos}

    def anuncia(s, para, vetor, saltos):
        return {d: (inf if poison and d != s and saltos.get(d) == para else c) for d, c in vetor.items()}

    ouvido = {a: {v: anuncia(v, a, dist[v], prox[v]) for v in viz[a]} for a in todos}
    for v in viz[caiu]:
        del viz[v][caiu]
        del ouvido[v][caiu]
    del viz[caiu]
    vivos = sorted(viz)
    atual = {a: dict(dist[a]) for a in vivos}
    saltos = {a: dict(prox[a]) for a in vivos}

    def passo():
        mudou = set()
        for a in vivos:
            vetor, s = {a: 0}, {}
            for d in todos:
                if d == a:
                    continue
                melhor, quem = inf, None
                for v in sorted(viz[a]):
                    if viz[a][v] + ouvido[a][v][d] < melhor:
                        melhor, quem = viz[a][v] + ouvido[a][v][d], v
                vetor[d], s[d] = melhor, quem
            if vetor != atual[a]:
                mudou.add(a)
            atual[a], saltos[a] = vetor, s
        return mudou

    mudou = passo()
    mensagens = rodadas = 0
    while mudou:
        rodadas += 1
        for s in mudou:
            for v in viz[s]:
                ouvido[v][s] = anuncia(s, v, atual[s], saltos[s])
                mensagens += 1
        mudou = passo()
    return rodadas, mensagens


def q2():
    print("\n== Q2: inundação")
    r = json_de("q2_inundacao")
    for rodada in r["rodadas"]:
        nome = "q2_inundacao" if rodada["rodada"] == 1 else "q2_repeticao_%d" % rodada["rodada"]
        c = contar_q2(nome)
        conferir("rodada %d: %d transmissões = %d aceitas + %d cópias + %d ao R4 (captura e logs)"
                 % (rodada["rodada"], c["transmissoes"], c["aceitos"], c["copias"], c["ao_r4"]),
                 c["gerados"] == 2 and c["outros"] == 0 and c["transmissoes"] == c["aceitos"] + c["copias"] + c["ao_r4"]
                 and (c["transmissoes"], c["aceitos"], c["copias"], c["ao_r4"]) ==
                 (rodada["transmissoes"], rodada["aceitos_como_novos"], rodada["descartados_copia"],
                  rodada["enviados_ao_R4_morto"]) and (c["aceitos"], c["copias"]) == (6, 4), (c, rodada))
        conferir("rodada %d: só os LSPs da queda na janela (0 extras, 0 renovações, 0 descartes de LSP antigo)" % rodada["rodada"],
                 (c["extras"], c["renovacoes"], c["antigos"]) == (0, 0, 0), c)
    # Fórmula do texto: 2E - (N - 1), na rede sem o R4
    e = {tuple(sorted(k)) for k in enlaces_das_configs() if 4 not in k}
    conferir("fórmula: sem R4, N = 4 e E = 4 dão 5 transmissões, 3 aceitas e 2 cópias por LSP",
             len(e) == 4 and 2 * len(e) - 3 == 5 and 2 * len(e) - 3 - 3 == 2)
    for extra in [x for d in r["por_lsp"].values() for x in d["caminho"] if x.endswith("->R4")]:
        quem = int(extra[1])
        lsp_chegou = [t for t, cat, txt in log("q2_inundacao", quem) if txt.startswith("LSP novo:")]
        detectou = min(t for t, cat, txt in log("q2_inundacao", quem) if "10.6.4.1" in txt and "INATIVO" in txt)
        conferir("R%d recebeu o LSP do outro vizinho antes de detectar a queda" % quem,
                 any(t <= detectou for t in lsp_chegou if t >= detectou - 1))
    for d in r["vetor_distancia"]:
        conta = dv_independente(4, d["poison_reverse"], d["infinito"])
        conferir("modelo DV (poison=%s, infinito=%d): %d rodadas, %d mensagens, conferido por outra implementação"
                 % (d["poison_reverse"], d["infinito"], d["rodadas"], d["mensagens"]),
                 conta == (d["rodadas"], d["mensagens"]), conta)


# ---------------------------------------------------------------------- Q3

def q3():
    print("\n== Q3: convergência")
    r = json_de("q3_resumo")
    for m in r["medidas"]:
        nome = "q3_convergencia_%d" % m["rodada"]
        lista = pacotes(nome)
        det = {n: min(t for t, cat, x in log(nome, n) if cat == "VIZINHO" and "10.6.2.1" in x and "INATIVO" in x)
               for n in (1, 3, 4)}
        primeira = min(det.values())
        queda = primeira - m["deteccao_s"]
        hello_captura = max(p["t"] for p in lista if p["de"] == 2 and p["txt"].startswith("HELLO") and p["t"] <= queda + 0.01)
        depois = [p for p in lista if p["de"] == 2 and p["t"] > queda + 0.05 and p["t"] < primeira]
        ultima = max(t for n in (1, 3, 4, 5) for t, cat, x in log(nome, n) if cat == "TABELA" and "MUDOU" in x and t >= queda)
        rota = min(t for t, cat, x in log(nome, 1) if cat == "TABELA" and t >= queda and "10.6.3.0/24 via 10.6.3.1 (custo 4)" in x)
        maiores = {}
        gerados = {(end(n), g) for n in (1, 3, 4) for _, cat, x in log(nome, n)
                   for g in re.findall(r"LSP proprio gerado \(vizinho 10\.6\.2\.1 ficou inativo\): seq (\d+)", x)}
        for p in lista:
            if p["txt"].startswith("LSP:") and tuple(p["txt"].split(":")[1:3]) in gerados and p["para"] != 2:
                maiores.setdefault(tuple(p["txt"].split(":")[1:3]), []).append(p["t"])
        inundacao = max(max(v) - min(v) for v in maiores.values()) * 1000
        renovacoes = sum(1 for n in (1, 3, 4, 5) for t, cat, x in log(nome, n)
                         if "renovacao periodica" in x and queda <= t <= ultima + 0.5)
        ok = (perto(primeira - hello_captura, m["primeira_deteccao_apos_ultimo_hello_s"], 0.01)
              and 20 <= primeira - hello_captura <= 20.6 and not depois
              and perto((max(det.values()) - primeira) * 1000, m["diferenca_entre_detectores_ms"], 1.1)
              and perto((ultima - primeira) * 1000, m["inundacao_e_recalculo_ms"], 1.1)
              and perto(rota - queda, m["rota_r1_r3_apos_queda_s"], 0.002)
              and perto(ultima - queda, m["total_s"], 0.002) and perto(inundacao, m["maior_inundacao_de_um_lsp_ms"], 0.01)
              and m["tabelas_finais_corretas"] and renovacoes == 0)
        conferir("rodada %d: detecção %.2f s, %.0f ms de inundação e recálculo, último HELLO a %.2f s da detecção"
                 % (m["rodada"], m["deteccao_s"], m["inundacao_e_recalculo_ms"], primeira - hello_captura), ok, m)
    ordem = sorted(r["medidas"], key=lambda x: x["queda_apos_ultimo_hello_s"])
    conferir("quanto mais tarde a queda em relação ao HELLO, menor a detecção",
             all(a["deteccao_s"] > b["deteccao_s"] for a, b in zip(ordem, ordem[1:])))
    conferir("detecção dentro da faixa teórica (15 a 20,5 s)",
             all(15 <= x["deteccao_s"] <= 20.5 for x in r["medidas"]))


# ---------------------------------------------------------------------- Q4

def q4():
    print("\n== Q4: números de sequência")
    r = json_de("q4_sequencia")
    linhas = log("q4_sequencia", 1)
    lista = [p for p in pacotes("q4_sequencia") if p["txt"].startswith("LSP:10.6.2.1:")]
    novo = [t for t, c, x in linhas if x.startswith("LSP novo: 10.6.2.1 seq %d " % r["seq_apos_reinicio_real"])]
    conferir("reinício real: seq novo > seq antigo, e o R1 aceitou",
             r["seq_apos_reinicio_real"] > r["seq_antigo_na_lsdb_do_r1"] and len(novo) == 1)
    envelheceu = [t for t, c, x in linhas if "LSP de 10.6.2.1 envelhecido" in x]
    conferir("o LSP antigo ainda estava na LSDB ao reiniciar (nenhum envelhecimento antes)",
             envelheceu and novo[0] < envelheceu[0] and r["lsp_antigo_ainda_na_lsdb_ao_reiniciar"])
    for seq in (0, 1, 2):
        conferir("seq %d: está na captura e foi descartado pelo R1" % seq,
                 any(p["txt"].startswith("LSP:10.6.2.1:%d:" % seq) and (p["de"], p["para"]) == (2, 1) for p in lista)
                 and any(x.startswith("LSP descartado (copia/antigo): 10.6.2.1 seq %d " % seq) for _, _, x in linhas)
                 and not any(x.startswith("LSP novo: 10.6.2.1 seq %d " % seq) for _, _, x in linhas))
    aceito3 = [t for t, c, x in linhas if x.startswith("LSP novo: 10.6.2.1 seq 3 ")]
    conferir("seq 3 só foi aceito depois do envelhecimento", len(aceito3) == 1 and aceito3[0] > envelheceu[0])
    ultima_renovacao = max(t for t, c, x in linhas if x.startswith("LSP novo: 10.6.2.1 seq %d " % r["seq_guardado_antes_dos_lsps_baixos"]))
    conferir("o envelhecimento ocorreu cerca de 90 s depois do último LSP aceito do R2",
             90 <= envelheceu[0] - ultima_renovacao <= 91, envelheceu[0] - ultima_renovacao)


# ---------------------------------------------------------------------- Q5

def q5():
    print("\n== Q5: confiabilidade")
    r = json_de("q5_confiabilidade")
    with open(os.path.join(AQUI, "evidencias", "q5_confiabilidade", "falhas_injetadas.txt"), encoding="ascii") as arquivo:
        perdas = [l.split() for l in arquivo]
    perdido = perdas[0][-1]
    t_perda = float(perdas[0][0])
    seq = int(perdido.split(":")[2])
    lista = pacotes("q5_confiabilidade")
    conferir("só um LSP foi perdido, e sem o R4 na lista",
             len({p[-1] for p in perdas}) == 1 and perdido.startswith("LSP:10.6.5.1:") and "10.6.4.1" not in perdido)
    conferir("a captura mostra as %d cópias chegando ao R1" % len(perdas),
             sum(p["txt"] == perdido and p["para"] == 1 for p in lista) == len(perdas) == 2)
    linhas = log("q5_confiabilidade", 1)
    conferir("o R1 não registrou esse LSP como recebido",
             not any(x.startswith("LSP novo: 10.6.5.1 seq %d " % seq) for _, _, x in linhas))
    conferir("a tabela do R1 tinha a rota fantasma para o R4 com custo 11",
             any(l.split()[0] == "10.6.4.0/24" and l.split()[2] == "11" for l in r["tabela_r1_com_lsdb_desatualizada"][1:]))
    conferir("a tabela do R3 não tinha rota para o R4",
             not any(l.startswith("10.6.4.0/24") for l in r["tabela_r3_no_mesmo_momento"]))
    conferir("o ICMP 3 do ping saiu do R2 para o R1 (captura)",
             any(p["de"] == 2 and p["para"] == 1 and p["txt"].startswith("ICMP:10.6.2.1:10.6.1.1:") and p["txt"].endswith(":3")
                 for p in lista))
    novos = [(t, x) for t, c, x in linhas if x.startswith("LSP novo: 10.6.5.1") and t > t_perda]
    renovou = [(t, x) for t, c, x in log("q5_confiabilidade", 5) if "renovacao periodica" in x and t > t_perda - 0.01]
    conferir("o primeiro LSP do R5 depois da perda veio de uma renovação periódica e já sem o R4",
             novos and renovou and ("seq %s " % novos[0][1].split()[4] in renovou[0][1]) and "10.6.4.1" not in novos[0][1],
             (novos[:1], renovou[:1]))
    conferir("tempo até a recuperação confere (%.2f s) e é menor que 30,5 s" % (novos[0][0] - t_perda),
             perto(novos[0][0] - t_perda, r["segundos_com_lsdb_desatualizada"], 0.01) and novos[0][0] - t_perda < 30.5)
    conferir("depois da recuperação o R1 não tem mais rota para o R4",
             not any(l.startswith("10.6.4.0/24") for l in r["tabela_r1_depois"]))


# ---------------------------------------------------------------------- Q6

def q6():
    print("\n== Q6: TTL e laço")
    r = json_de("q6_ttl_laco")
    def rota(tabela):
        return next(l.split()[1] for l in tabela if l.startswith("10.6.1.0/24"))
    d = r["tabelas_durante_o_laco"]
    conferir("durante o laço: R2 aponta para R3 e R3 aponta para R2",
             rota(d["R2"]) == end(3) and rota(d["R3"]) == end(2))
    lista = pacotes("q6_ttl_laco")
    ida = [p for p in lista if re.match(r"ICMP:10\.6\.5\.1:10\.6\.1\.1:\d+:1:8$", p["txt"])]
    ttl = [int(p["txt"].split(":")[3]) for p in ida]
    conferir("o pedido aparece 16 vezes na captura, com TTL de 16 a 1", ttl == list(range(16, 0, -1)), ttl)
    enlaces = [(p["de"], p["para"]) for p in ida]
    conferir("caminho: R5->R3 e depois R3<->R2 alternando",
             enlaces == [(5, 3)] + [(3, 2) if i % 2 == 0 else (2, 3) for i in range(15)], enlaces)
    erro = [p for p in lista if re.match(r"ICMP:10\.6\.2\.1:10\.6\.5\.1:\d+:1:11$", p["txt"])]
    conferir("o R2 gerou o ICMP 11 com TTL 16 e id 1", erro and erro[0]["de"] == 2 and erro[0]["txt"].split(":")[3] == "16")
    conferir("o R5 exibiu tempo excedido informado pelo R2",
             r["ping_r5_para_r1_durante"][0].startswith("Tempo excedido informado por 10.6.2.1"))
    conferir("depois da convergência: R3 vai direto ao R1 e o ping responde",
             rota(r["tabelas_depois"]["R3"]) == end(1) and r["ping_r5_para_r1_depois"][0].startswith("Resposta de eco de 10.6.1.1"))
    with open(os.path.join(AQUI, "evidencias", "q6_ttl_laco", "falhas_injetadas.txt"), encoding="ascii") as arquivo:
        falhas = [l.split() for l in arquivo]
    conferir("as falhas injetadas foram só o corte R1-R2 e o atraso do LSP do R2 ao R3",
             all((f[1], f[4].split(":")[1]) in (("10.6.1.1", "6002"), ("10.6.2.1", "6001"))
                 or (f[1] == "10.6.3.1" and f[5].startswith("LSP:10.6.2.1:")) for f in falhas), falhas[:2])


# ---------------------------------------------------------------------- Anexo A

def anexo():
    print("\n== Anexo A: cada filtro do Wireshark encontra os pacotes")
    r = json_de("q2_inundacao")
    filtro_q2 = r["filtro"]
    casos = [("q1_dijkstra", 'udp contains "LSP"', None), ("q2_inundacao", filtro_q2, r["total"]["transmissoes"])]
    casos += [(os.path.basename(x["captura"])[:-7], x["filtro"], x["transmissoes"]) for x in r["rodadas"][1:]]
    casos += [("q3_convergencia_%d" % k, 'udp contains "HELLO:10.6.2.1"', None) for k in range(1, 6)]
    casos += [("q4_sequencia", 'udp contains "LSP:10.6.2.1:0:"', 1), ("q5_confiabilidade", 'udp contains "LSP:10.6.5.1"', None),
              ("q6_ttl_laco", 'udp contains "ICMP:10.6.5.1:10.6.1.1"', None)]
    for nome, filtro, esperado in casos:
        saida = subprocess.run([TSHARK, "-r", os.path.join(AQUI, "capturas", nome + ".pcapng"), "-Y", filtro, "-T", "fields",
                                "-e", "frame.number"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               universal_newlines=True, check=True).stdout.split()
        conferir("%s: filtro encontrou %d pacotes" % (nome, len(saida)), saida and (esperado is None or len(saida) == esperado))


# ---------------------------------------------------------------------- prints do Wireshark

def prints():
    print("\n== Prints reais do Wireshark")
    from PIL import Image
    sys.path.insert(0, AQUI)
    from tira_prints import assinatura, casos
    caminho_registro = os.path.join(AQUI, "figuras", "prints.json")
    registro = {}
    if os.path.exists(caminho_registro):
        with open(caminho_registro, encoding="utf-8") as arquivo:
            registro = json.load(arquivo)
    for chave, (captura, filtro) in casos().items():
        arquivo = os.path.join(AQUI, "figuras", "wireshark_%s.png" % chave)
        origem = os.path.join(AQUI, "capturas", captura + ".pcapng")
        linhas = subprocess.run([TSHARK, "-r", origem, "-Y", filtro, "-T", "fields", "-e", "frame.number"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True, check=True).stdout.split()
        imagem = Image.open(arquivo).convert("RGB")
        fim = max(y for y in range(200, imagem.height - 60) if imagem.getpixel((1900, y))[0] > 190)
        no_print = round((fim - 216) / 36)
        mesma = registro.get(chave, {}).get("sha256") == assinatura(captura) and registro.get(chave, {}).get("filtro") == filtro
        conferir("%s: print de %s mostra as %d linhas do filtro e foi tirado desta captura" % (chave, captura, len(linhas)),
                 no_print == len(linhas) and mesma, (no_print, len(linhas), "registro confere" if mesma else "registro nao confere"))
    lista = subprocess.run(["pdfimages", "-list", os.path.join(AQUI, "relatorio.pdf")], stdout=subprocess.PIPE,
                           universal_newlines=True, check=True).stdout.splitlines()[2:]
    grandes = [l for l in lista if l.split()[2] == "image" and int(l.split()[3]) >= 1900]
    conferir("o PDF contém os 5 prints em resolução cheia", len(grandes) >= 5, len(grandes))


# ---------------------------------------------------------------------- PDF

def pdf():
    print("\n== PDF: números impressos")
    texto = subprocess.run(["pdftotext", "-layout", os.path.join(AQUI, "relatorio.pdf"), "-"],
                           stdout=subprocess.PIPE, universal_newlines=True, check=True).stdout
    corrido = re.sub(r"-\n\s*", "", texto)
    corrido = re.sub(r"\s+", " ", corrido)
    br = lambda x, c: ("%.*f" % (c, x)).replace(".", ",")
    def tem(nome, *itens):
        faltando = [i for i in itens if i not in corrido]
        conferir("PDF contém: " + nome, not faltando, faltando)
    enunciado = ["Questão 1: Dijkstra", "Questão 2: inundação", "Questão 3: convergência", "Questão 4: números de sequência",
                 "Questão 5: confiabilidade", "Questão 6: TTL", "Figura 1", "Figura 2", "Figura 3", "Figura 4", "Figura 5", "Figura 6", "Anexo A"]
    tem("as 6 questões, a figura e o anexo", *enunciado)
    q = json_de("q2_inundacao")
    tem("Q2", "circularam %d pacotes LSP" % q["total"]["transmissoes"], "pacotes têm origem e destino 127.0.0.1", "macOS", "%d foram descartados" % q["total"]["descartados_copia"],
        *[str(p["seq"]) for p in q["por_lsp"].values()])
    for d in q["vetor_distancia"]:
        if not re.search(r"infinito = %d %d %d" % (d["infinito"], d["rodadas"], d["mensagens"]), corrido):
            conferir("PDF contém a linha DV %s" % d, False)
    m = json_de("q3_resumo")
    tem("Q3", *[br(x["deteccao_s"], 2) for x in m["medidas"]], *[br(x["total_s"], 2) for x in m["medidas"]])
    q4r = json_de("q4_sequencia")
    tem("Q4", str(q4r["seq_antigo_na_lsdb_do_r1"]), str(q4r["seq_apos_reinicio_real"]))
    tem("Q5", br(json_de("q5_confiabilidade")["segundos_com_lsdb_desatualizada"], 2))
    tem("Q6", json_de("q6_ttl_laco")["ping_r5_para_r1_durante"][0])
    # A última é da versão do William (D53): eram 11 transmissões em cada rodada, não nas 5 juntas
    for frase in ["até três HELLOs", "uma ou duas renovações", "no mesmo instante, já", "à mão", "ficaram de fora",
                  "11 transmissões nas 5 rodadas"]:
        conferir("frase corrigida não aparece mais: " + frase, frase not in corrido)


if __name__ == "__main__":
    base()
    q1()
    q2()
    q3()
    q4()
    q5()
    q6()
    anexo()
    prints()
    pdf()
    print("\nRESUMO: %d verificacoes, %d falharam" % (len(resultados), resultados.count(False)))
    sys.exit(1 if False in resultados else 0)
