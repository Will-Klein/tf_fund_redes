"""Gera docs/relatorio/relatorio.pdf: o texto das respostas com os números medidos.

Os números vêm de evidencias/*/resultado.json, dos logs e das capturas; nada é copiado à mão. Se um
experimento for refeito, basta rodar este script de novo. O PDF é impresso pelo WebKit do macOS
(imprime_pdf.swift, compilado na hora) e numerado com pypdf e matplotlib.

Uso, da raiz do repositório: python3 docs/relatorio/gera_relatorio.py
"""

import base64
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from experimentos import TSHARK  # noqa: E402
from tira_prints import assinatura, casos as filtros_dos_prints  # noqa: E402

SAIDA = os.path.join(AQUI, "relatorio.pdf")
DISCIPLINA = "Fundamentos de Redes de Computadores"
INTEGRANTES = ["William de Oliveira Klein", "Gustavo de Freitas Fidélis", "Frederico Abreu Miguens Nizoli"]

CSS = """
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font: 10.8pt/1.45 Charter, 'Times New Roman', serif; color: #1a1a1a; margin: 0; }
.capa { height: 215mm; display: flex; flex-direction: column; justify-content: center; text-align: center;
        page-break-after: always; }
.capa .inst { font: 11pt 'Helvetica Neue', Arial, sans-serif; letter-spacing: .04em; color: #444; }
.capa h1 { font: 700 25pt/1.2 'Helvetica Neue', Arial, sans-serif; color: #1F4E79; margin: 18mm 0 4mm; }
.capa .sub { font-size: 14pt; color: #333; margin-bottom: 26mm; }
.capa .grupo { font-size: 12pt; line-height: 1.7; }
h2, h3 { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1F4E79; page-break-after: avoid; }
h2 { font-size: 15pt; margin: 8mm 0 3mm; padding-bottom: 1.2mm; border-bottom: 1.2pt solid #1F4E79; }
h2.nova { margin-top: 9mm; }
h2.pagina { page-break-before: always; margin-top: 0; }
ul { page-break-inside: avoid; }
.bloco { page-break-inside: avoid; }
h3 { font-size: 11pt; margin: 5mm 0 1.5mm; color: #2B2B2B; }
p { margin: 0 0 2.6mm; text-align: justify; hyphens: auto; }
ul { margin: 0 0 2.6mm; padding-left: 5mm; } li { margin-bottom: 1mm; }
code, pre { font-family: Menlo, 'DejaVu Sans Mono', monospace; }
code { font-size: 8.8pt; background: #F0F2F4; padding: 0 2px; border-radius: 2px; }
pre { font-size: 7.9pt; line-height: 1.38; background: #F5F6F8; border-left: 2.2pt solid #1F4E79;
      padding: 2mm 3mm; margin: 1mm 0 3mm; white-space: pre-wrap; overflow-wrap: anywhere; page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 1mm 0 3.2mm; font: 8.6pt/1.3 'Helvetica Neue', Arial, sans-serif;
        page-break-inside: avoid; }
th { color: #1F4E79; font-weight: 700; text-align: left; padding: 1.2mm 1.6mm; border-top: 1pt solid #1F4E79;
     border-bottom: 1pt solid #1F4E79; vertical-align: bottom; }
td { padding: 1mm 1.6mm; border-bottom: .5pt solid #C9CED3; vertical-align: top; }
tr.total td { font-weight: 700; border-top: 1pt solid #1F4E79; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.leg { font: italic 8.6pt 'Helvetica Neue', Arial, sans-serif; color: #555; margin: -1.6mm 0 3.2mm; }
figure { margin: 2mm 0 3mm; text-align: center; page-break-inside: avoid; }
figure img { width: 98mm; }
figure.print { margin: 2mm 0 3.2mm; }
figure.print img { width: 100%; border-radius: 1.5mm; }
figcaption { font: italic 8.8pt 'Helvetica Neue', Arial, sans-serif; color: #555; }
.lado { display: flex; gap: 4mm; page-break-inside: avoid; } .lado > div { flex: 1; min-width: 0; }
.rot { font: 600 8.6pt 'Helvetica Neue', Arial, sans-serif; color: #333; margin-bottom: .6mm; }
.nota { background: #EEF4FA; border-left: 2.2pt solid #1F4E79; padding: 2mm 3mm; margin: 2mm 0 3mm; font-size: 9.8pt;
        page-break-inside: avoid; }
.nota p:last-child { margin-bottom: 0; }
"""


def ler(nome):
    with open(os.path.join(AQUI, "evidencias", nome, "resultado.json"), encoding="utf-8") as arquivo:
        return json.load(arquivo)


def n(valor, casas=1):
    """Número com vírgula decimal: 17.268 -> '17,3'."""
    return ("%.*f" % (casas, valor)).replace(".", ",")


def pre(linhas):
    return "<pre>" + html.escape("\n".join(linhas)) + "</pre>"


def tab(cabecalho, linhas, numericas=(), classe_linha=None):
    """Tabela HTML. 'numericas': índices das colunas alinhadas à direita."""
    def classe(i):
        return ' class="num"' if i in numericas else ""
    saida = ["<table><tr>" + "".join("<th%s>%s</th>" % (classe(i), c) for i, c in enumerate(cabecalho)) + "</tr>"]
    for k, linha in enumerate(linhas):
        extra = ' class="%s"' % classe_linha(k) if classe_linha and classe_linha(k) else ""
        saida.append("<tr%s>" % extra + "".join("<td%s>%s</td>" % (classe(i), c) for i, c in enumerate(linha)) + "</tr>")
    return "".join(saida) + "</table>"


def quadros(captura, filtro):
    """[(nº do quadro, roteador de origem, roteador de destino, texto)] que passam no filtro do Wireshark."""
    saida = subprocess.run([TSHARK, "-r", os.path.join(AQUI, captura), "-Y", filtro, "-T", "fields",
                            "-e", "frame.number", "-e", "udp.srcport", "-e", "udp.dstport", "-e", "udp.payload"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
                           check=True).stdout
    resultado = []
    for linha in saida.splitlines():
        q, de, para, carga = linha.split("\t")
        resultado.append((int(q), int(de) - 6000, int(para) - 6000, bytes.fromhex(carga).decode("ascii")))
    return resultado


def conferir_print(chave):
    """Impede um PDF com print de uma captura antiga: compara com o registro de tira_prints.py."""
    captura, filtro = filtros_dos_prints()[chave]
    try:
        with open(os.path.join(AQUI, "figuras", "prints.json"), encoding="utf-8") as arquivo:
            registro = json.load(arquivo)[chave]
    except (OSError, KeyError):
        sys.exit("Falta o print %s: rode python3 docs/relatorio/tira_prints.py" % chave)
    if (registro["sha256"], registro["filtro"]) != (assinatura(captura), filtro):
        sys.exit("O print %s nao corresponde a captura atual: rode python3 docs/relatorio/tira_prints.py" % chave)


def print_wireshark(chave, numero, legenda):
    """Print real da janela do Wireshark, cortando só a área vazia abaixo da lista de pacotes."""
    from PIL import Image
    conferir_print(chave)
    imagem = Image.open(os.path.join(AQUI, "figuras", "wireshark_%s.png" % chave)).convert("RGB")
    fim = max(y for y in range(200, imagem.height - 60) if imagem.getpixel((1900, y))[0] > 190)
    memoria = io.BytesIO()
    imagem.crop((0, 0, imagem.width, fim + 6)).save(memoria, "PNG", optimize=True)
    return ('<figure class="print"><img src="data:image/png;base64,%s" alt="Print do Wireshark">'
            "<figcaption>Figura %d. %s</figcaption></figure>"
            % (base64.b64encode(memoria.getvalue()).decode(), numero, legenda))


def aceitos_no_log(pasta, origem, seq):
    """{(de, para)} das transmissões deste LSP que o roteador 'para' aceitou como novas."""
    aceitos = set()
    for para in (1, 2, 3, 5):
        caminho = os.path.join(AQUI, "evidencias", pasta, "logs_roteadores", "10.6.%d.1.log" % para)
        with open(caminho, encoding="ascii") as arquivo:
            for linha in arquivo:
                m = re.search(r"LSP novo: %s seq %d .*, de 10\.6\.(\d)\.1 \(" % (re.escape(origem), seq), linha)
                if m:
                    aceitos.add((int(m.group(1)), para))
    return aceitos


def linhas_do_log(pasta, roteador):
    caminho = os.path.join(AQUI, "evidencias", pasta, "logs_roteadores", "10.6.%d.1.log" % roteador)
    with open(caminho, encoding="ascii") as arquivo:
        return [linha.rstrip("\n") for linha in arquivo]


# ---------------------------------------------------------------------- seções

def capa():
    nomes = " &middot; ".join(INTEGRANTES) if max(len(x) for x in INTEGRANTES) < 12 else "<br>".join(INTEGRANTES)
    return f"""<div class="capa">
<div class="inst">PUCRS &middot; {DISCIPLINA}</div>
<h1>Roteador de estado de enlace<br>sobre UDP</h1>
<div class="sub">Relatório do trabalho final</div>
<div class="grupo"><b>Grupo 6</b><br>{nomes}<br><br>Novembro de 2026</div>
</div>"""


def metodologia():
    figura = open(os.path.join(AQUI, "figuras", "topologia_local5.png"), "rb").read()
    return f"""<h2>1. Introdução, topologia e método</h2>
<p>Este relatório apresenta os experimentos do roteador de estado de enlace implementado pelo grupo, uma aplicação
sobre UDP inspirada no OSPF. Cada roteador descobre os vizinhos com HELLO, inunda LSPs, mantém a LSDB com a topologia
completa, calcula a tabela com o algoritmo de Dijkstra e encaminha pacotes de dados e ICMP com controle de TTL. As seções
seguintes respondem às seis questões do enunciado, com logs, saídas dos comandos e capturas do Wireshark.</p>
<p>A rede de teste tem <b>5 roteadores</b> e 6 enlaces, todos com custos diferentes (Figura 1). Um teste automatizado
(<code>tests/test_dijkstra.py</code>) confirma que nenhum par de roteadores tem dois caminhos de custo mínimo, então cada rota
esperada é única. Há caminhos alternativos: de R1 a R3, por exemplo, o melhor caminho passa por R2
(custo 1 + 2 = 3), e o enlace direto (custo 4) assume quando R2 cai. Cada roteador <code>R</code> tem o endereço
virtual <code>10.6.R.1</code> e responde pela rede <code>10.6.R.0/24</code>.</p>
<figure><img src="data:image/png;base64,{base64.b64encode(figura).decode()}" alt="Topologia com 5 roteadores">
<figcaption>Figura 1. Topologia de teste, com os custos dos enlaces, os endereços virtuais e as portas UDP.</figcaption></figure>
<p>Os experimentos foram feitos em uma única máquina com macOS, como o enunciado permite; o ambiente da apresentação é outro (VMs
Windows da VDI, com um roteador por integrante). Foram 5 processos do roteador (Python 3.9) em
<code>127.0.0.1</code>, nas portas 6001 a 6005, com os temporizadores da especificação (HELLO a cada 5 s, vizinho
inativo após 20 s, renovação do LSP a cada 30 s e envelhecimento em 90 s). O tráfego foi capturado na interface
de loopback com o Wireshark 4.6.7. As contagens e os tempos foram extraídos das capturas e dos logs dos roteadores. As Figuras 2 a 6 são prints reais da janela do
Wireshark com as capturas entregues; acrescentamos uma coluna com o conteúdo do pacote e cortamos só a área vazia abaixo da lista.
O Anexo A lista cada captura entregue e o filtro para reproduzir as tabelas no Wireshark.</p>
<div class="nota"><p><b>Duas observações sobre as evidências.</b> (1) Em loopback, um pacote não se perde sozinho.
Por isso, nas questões 5 e 6, a perda e o atraso de LSPs foram <b>simulados</b> por um embrulho do socket usado só
nos experimentos (<code>docs/relatorio/sobe_com_filtro.py</code>); o código do roteador não foi alterado.
(2) Não implementamos um protocolo de vetor de distância. A comparação da questão 2 usa um <b>modelo simples</b>,
identificado como tal.</p></div>"""


def q1():
    r = ler("q1_dijkstra")
    assert r["igual_ao_programa"]
    nos = ["R2", "R3", "R4", "R5"]
    linhas = []
    finalizados = {"R1"}
    for it in r["iteracoes"]:
        celulas = []
        for v in nos:
            texto = "&infin;" if it["D"][v] == "inf" else it["D"][v]
            if v == it["escolhido"]:
                celulas.append('<span style="font-weight:700;color:#1F4E79">%s</span>' % texto)
            elif v in finalizados:
                celulas.append('<span style="color:#7A828A">%s</span>' % texto)
            else:
                celulas.append(texto)
        linhas.append([it["passo"], ", ".join(it["N"])] + celulas)
        finalizados.add(it["escolhido"])
    final = r["iteracoes"][-1]["D"]

    def caminho(v):
        trecho = [v]
        while trecho[0] != "R1":
            trecho.insert(0, final[trecho[0]].split(",")[1])
        return " &rarr; ".join(trecho)

    programa = {}
    for linha in r["tabela_r1"][1:]:
        rede, prox, custo = linha.split()
        programa[rede] = (prox, int(custo))
    comparacao = []
    for v in nos:
        rede = "10.6.%s.0/24" % v[1]
        prox_mao, custo_mao = r["rotas_a_mao"][rede]
        comparacao.append([rede, caminho(v), "%s / %d" % (prox_mao, custo_mao),
                           "%s / %d" % programa[rede], "igual" if (prox_mao, custo_mao) == programa[rede] else "DIFERENTE"])
    return f"""<h2 class="pagina">2. Questão 1: Dijkstra</h2>
<p>Usamos o roteador <b>R1</b>. Depois da convergência, o comando <code>lsdb</code> mostrou a base abaixo. Cada linha
é o LSP de uma origem, e cada item <code>vizinho=custo</code> é uma aresta dirigida do grafo.</p>
{pre(r["lsdb_r1"])}
<p>A Tabela 1 executa o algoritmo a partir de R1, como na aula. <code>N'</code> é o conjunto de nós já finalizados, e
cada célula é <code>D(v),p(v)</code>: o menor custo conhecido até <code>v</code> e o nó anterior no caminho.</p>
{tab(["Passo", "N'", "R2", "R3", "R4", "R5"], linhas, numericas=(0,))}
<div class="leg">Tabela 1. Iterações do Dijkstra em R1. Em azul, o nó escolhido no passo; em cinza, os já finalizados.</div>
<ul>
<li><b>Passo 0:</b> só os vizinhos de R1 têm custo conhecido: R2 = 1 e R3 = 4.</li>
<li><b>Passo 1:</b> entra R2 (custo 1). Passando por ele, R3 cai de 4 para 1 + 2 = 3, e R4 passa a 1 + 7 = 8.</li>
<li><b>Passo 2:</b> entra R3 (custo 3). R5 passa a 3 + 3 = 6.</li>
<li><b>Passo 3:</b> entra R5 (custo 6). Por ele, R4 custaria 6 + 5 = 11, pior que 8, e nada muda.</li>
<li><b>Passo 4:</b> entra R4 (custo 8), e o algoritmo termina.</li>
</ul>
<p>Seguindo os predecessores até R1, obtemos o caminho e o próximo salto de cada destino. A Tabela 2 compara esse
resultado com o comando <code>tabela</code> do programa, cuja saída foi:</p>
{pre(r["tabela_r1"])}
{tab(["Rede", "Caminho", "Dijkstra (próx. salto / custo)", "Programa (próx. salto / custo)", "Resultado"], comparacao)}
<div class="leg">Tabela 2. Resultado do passo a passo comparado com a saída do comando <code>tabela</code> em R1.</div>
<p><b>As quatro rotas são iguais</b>, tanto no próximo salto quanto no custo.</p>"""


def q2():
    r = ler("q2_inundacao")
    t = r["total"]
    linhas = []
    conteudo = []
    copias_log = []
    # Na ordem em que os LSPs apareceram na captura (quem detectou a queda primeiro vem antes)
    ordem = sorted(r["por_lsp"].items(), key=lambda item: quadros(r["captura"], 'udp contains "LSP:10.6.%s.1:%d"'
                                                                  % (item[0][1], item[1]["seq"]))[0][0])
    for nome, d in ordem:
        origem = "10.6.%s.1" % nome[1]
        aceitos = aceitos_no_log("q2_inundacao", origem, d["seq"])
        pacotes = quadros(r["captura"], 'udp contains "LSP:%s:%d"' % (origem, d["seq"]))
        assert len(pacotes) == d["transmissoes"]
        conteudo.append(pacotes[0][3])
        contagem = {"aceito": 0, "cópia": 0, "morto": 0}
        for q, de, para, _ in pacotes:
            if para == 4:
                destino, chave = "enviado ao R4, que já caiu", "morto"
            elif (de, para) in aceitos:
                destino, chave = "aceito como novo", "aceito"
            else:
                destino, chave = "descartado como cópia", "cópia"
            contagem[chave] += 1
            linhas.append([nome, q, "R%d &rarr; R%d" % (de, para), destino])
        assert (contagem["aceito"], contagem["cópia"], contagem["morto"]) == (
            d["aceitos_como_novos"], d["descartados_copia"], d["enviados_ao_R4_morto"])
        trecho = "LSP descartado (copia/antigo): %s seq %d " % (origem, d["seq"])
        for roteador in (1, 2, 3, 5):
            copias_log += ["R%d: %s" % (roteador, l) for l in linhas_do_log("q2_inundacao", roteador) if trecho in l]
    assert len(copias_log) == t["descartados_copia"]
    linhas.append(["Total", "", "%d transmissões" % t["transmissoes"],
                   "%d aceitas, %d cópias, %d ao R4 caído" % (t["aceitos_como_novos"], t["descartados_copia"],
                                                               t["enviados_ao_R4_morto"])])

    # Transmissão a mais, se houve: quem reenviou ao R4 ainda não tinha detectado a queda
    extra = ""
    for nome, d in r["por_lsp"].items():
        for trecho in d["caminho"]:
            if trecho.endswith("->R4"):
                extra = (" A transmissão a mais desta rodada ocorreu porque %s recebeu o LSP de %s antes de seu próprio "
                         "temporizador expirar, quando R4 ainda constava como ativo." % (trecho.split("->")[0], nome))

    rodadas = r["rodadas"]
    assert all(x["aceitos_como_novos"] == 6 and x["descartados_copia"] == 4 and x["descartados_antigos"] == 0
               and x["lsps_extras_na_janela"] == 0 for x in rodadas)
    assert all(x["transmissoes"] == 10 + x["enviados_ao_R4_morto"] for x in rodadas)
    totais = sorted({x["transmissoes"] for x in rodadas})
    faixa = str(totais[0]) if len(totais) == 1 else "%d a %d" % (totais[0], totais[-1])
    linhas_rodadas = [[x["rodada"], n(x["queda_apos_a_partida_s"], 2), x["transmissoes"], x["aceitos_como_novos"],
                       x["descartados_copia"], x["enviados_ao_R4_morto"], x["lsps_extras_na_janela"]] for x in rodadas]
    if len(totais) == 1:
        variacao = "O total foi %d nas %d rodadas." % (totais[0], len(rodadas))
    else:
        variacao = "O total variou de %d a %d." % (totais[0], totais[-1])
    variacao += (" Pela fórmula, o total é 10; a 11ª transmissão só ocorre quando um vizinho de R4 recebe o LSP do outro "
                 "antes de detectar a queda.")
    dv = r["vetor_distancia"]
    nome_dv = lambda d: "Vetor de distância, %s, infinito = %d" % ("<i>poison reverse</i>" if d["poison_reverse"] else "sem proteção",
                                                                   d["infinito"])
    linhas_dv = [[nome_dv(d), d["rodadas"], d["mensagens"]] for d in dv]
    return f"""<h2 class="pagina">3. Questão 2: inundação</h2>
<p>Com a rede convergida, derrubamos o roteador <b>R4</b>. Escolhemos R4 porque, sem ele, ainda resta o ciclo
R1-R2-R3; numa rede sem ciclos não apareceriam cópias. A mudança gerou <b>{r["lsps_gerados_pela_mudanca"]} LSPs</b>,
um de cada vizinho de R4 (R2 e R5), {n(r["segundos_entre_queda_e_primeiro_lsp"])} s depois da queda, quando o temporizador
de 20 s expirou. Para medir só o efeito dessa mudança, cada queda ocorreu entre 31 e 36 s após a partida dos roteadores: assim, a
detecção não coincide com as renovações periódicas de 30 s e 60 s, e a janela da queda não contém nenhum outro LSP (Tabela 4). O
conteúdo dos dois LSPs, lido na captura, já não lista R4:</p>
{pre(conteudo)}
{tab(["LSP de", "Quadro", "Transmissão", "O que aconteceu"], linhas, numericas=(1,),
     classe_linha=lambda k: "total" if k == len(linhas) - 1 else "")}
<div class="leg">Tabela 3. Todas as transmissões dos dois LSPs na rodada 1, na captura <code>{r["captura"]}</code>.</div>
<div class="bloco"><p>A Figura 2 mostra essas transmissões no Wireshark. Todos os pacotes têm origem e destino <code>127.0.0.1</code>, pois os
roteadores rodam na mesma máquina; por isso, em todos os prints, a porta 600R identifica o roteador R. A última coluna é o conteúdo do pacote.</p>
{print_wireshark("q2", 2, "Wireshark: as %d transmissões dos dois LSPs gerados pela queda de R4 (<code>q2_inundacao.pcapng</code>)." % t["transmissoes"])}</div>
<p>Os logs confirmam as cópias: cada roteador registrou o descarte pela regra 2 do recebimento.</p>
{pre(copias_log)}
<p><b>Nesta rodada circularam {t["transmissoes"]} pacotes LSP, e {t["descartados_copia"]} foram descartados como cópias.</b> A conta
fecha com a regra de inundação. Em uma rede com <i>N</i> roteadores e <i>E</i> enlaces, a origem envia a todos os vizinhos e cada
um dos outros <i>N</i> &minus; 1 reenvia a todos, menos a quem lhe entregou. Isso dá 2<i>E</i> &minus; (<i>N</i> &minus; 1)
transmissões por LSP, das quais <i>N</i> &minus; 1 são aceitas e o restante é descartado como cópia. Sem R4, <i>N</i> = 4 e
<i>E</i> = 4: são <b>5 transmissões, 3 aceitas e 2 cópias por LSP</b>, ou 10 transmissões para os dois LSPs.{extra}</p>
<p>Repetimos a mesma queda {len(rodadas)} vezes para verificar se o resultado se mantém. Em todas as rodadas houve
<b>6 LSPs aceitos e 4 cópias descartadas</b>. {variacao}</p>
{tab(["Rodada", "Queda após a partida (s)", "Transmissões", "Aceitas", "Cópias descartadas", "Enviadas ao R4 caído", "Outros LSPs na janela"],
     linhas_rodadas, numericas=(0, 1, 2, 3, 4, 5, 6))}
<div class="leg">Tabela 4. Repetições da queda de R4 (capturas <code>q2_inundacao</code> e <code>q2_repeticao_2</code> a <code>{len(rodadas)}</code>).</div>
<div class="bloco"><h3 class="manual">Comparação com vetor de distância</h3>
<p>Em vetor de distância, cada roteador conhece apenas o custo até cada destino, informado pelos vizinhos. Modelamos a mesma
queda em rodadas síncronas: a cada rodada, quem mudou envia seu vetor inteiro a cada vizinho vivo. O valor 16 é o infinito usado
pelo RIP; o valor 64 mostra o efeito de um limite maior.</p>
{tab(["Protocolo", "Rodadas", "Mensagens"],
     [["<b>Estado de enlace (medido)</b>", "1 inundação por LSP", "<b>%s</b>" % faixa]] + linhas_dv, numericas=(2,))}
<div class="leg">Tabela 5. Mensagens após a queda de R4. As linhas de vetor de distância são de um modelo, não de medição.</div></div>
<p>O vetor de distância gasta mais mensagens aqui por causa da <b>contagem até o infinito</b>: ao perder R4, R2 aprende com R1,
e R5 aprende com R3, uma rota para R4 que, na verdade, passava por eles mesmos. Os custos sobem aos poucos, rodada a rodada, até o valor
adotado como infinito; por isso o total cresce quando esse limite aumenta. O <i>poison reverse</i> reduz o problema, mas não o
elimina, porque o laço envolve mais de dois roteadores. No estado de enlace, cada LSP descreve só os vizinhos da origem e
é inundado uma vez, e cada roteador recalcula sozinho: o número de mensagens depende da topologia, não dos custos. A
contrapartida é que todo roteador recebe todo LSP e guarda a topologia completa.</p>"""


def q3():
    r = ler("q3_resumo")
    s = r["resumo"]
    rotas = [m["rota_r1_r3_apos_queda_s"] for m in r["medidas"]]
    linhas = [[m["rodada"], n(m["queda_apos_ultimo_hello_s"], 2), n(m["deteccao_s"], 2), n(m["rota_r1_r3_apos_queda_s"], 2),
               n(m["inundacao_e_recalculo_ms"], 0), n(m["maior_inundacao_de_um_lsp_ms"], 2), n(m["total_s"], 2)]
              for m in r["medidas"]]
    linhas.append(["Média", "", n(s["deteccao_s"]["media"], 2), n(sum(rotas) / len(rotas), 2),
                   n(s["inundacao_e_recalculo_ms"]["media"], 0), n(s["maior_inundacao_de_um_lsp_ms"]["media"], 2),
                   n(s["total_s"]["media"], 2)])
    linhas_print = subprocess.run([TSHARK, "-r", os.path.join(AQUI, "capturas", "q3_convergencia_1.pcapng"), "-Y", filtros_dos_prints()["q3"][1],
                                   "-T", "fields", "-e", "frame.time_relative", "-e", "udp.payload"], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, universal_newlines=True, check=True).stdout.splitlines()
    tempos = [(float(l.split("\t")[0]), bytes.fromhex(l.split("\t")[1]).decode("ascii")) for l in linhas_print]
    intervalo_print = min(t for t, x in tempos if x.startswith("LSP:")) - max(t for t, x in tempos if x.startswith("HELLO:"))
    log_r1 = linhas_do_log("q3_convergencia_1", 1)
    i = next(k for k, l in enumerate(log_r1) if "[VIZINHO] 10.6.2.1" in l and "INATIVO" in l)
    trecho_log = log_r1[i:i + 3]
    fracao = s["deteccao_s"]["media"] / s["total_s"]["media"] * 100
    assert all(m["tabelas_finais_corretas"] for m in r["medidas"])
    return f"""<h2 class="nova">4. Questão 3: convergência</h2>
<p>Derrubamos <b>R2</b>, que está no caminho de R1 para R3, R4 e R5. Depois da reconvergência, R1 passa a alcançar R3 pelo
enlace direto (custo 3 &rarr; 4), R5 por R3 (6 &rarr; 7) e R4 por R3 e R5 (8 &rarr; 12). Repetimos o experimento
<b>5 vezes</b>, com a queda em momentos diferentes em relação ao último HELLO de R2, sempre entre 31 e 36 s após a partida para não
coincidir com as renovações de 30 s e 60 s, e separamos o tempo em duas partes:</p>
<ul><li><b>Detecção:</b> da queda até o primeiro vizinho declarar R2 inativo;</li>
<li><b>Inundação e recálculo:</b> dessa primeira detecção até a última mudança de tabela na rede.</li></ul>
{tab(["Rodada", "Queda após o último HELLO (s)", "Detecção (s)", "Rota R1&rarr;R3 recalculada (s)", "Inundação + recálculo (ms)",
      "Maior inundação de um LSP (ms)", "Total na rede (s)"],
     linhas, numericas=(0, 1, 2, 3, 4, 5, 6), classe_linha=lambda k: "total" if k == len(linhas) - 1 else "")}
<div class="leg">Tabela 6. Tempos de convergência após a queda de R2 (capturas <code>q3_convergencia_1</code> a <code>5</code>).</div>
<div class="bloco"><p>A Figura 3 mostra a rodada 1 no Wireshark: os HELLOs de R2 (porta 6002) param e, {n(intervalo_print, 2)} s
depois do último deles, os vizinhos inundam os LSPs que já não listam R2.</p>
{print_wireshark("q3", 3, "Wireshark: HELLOs de R2 e LSPs da queda (<code>q3_convergencia_1.pcapng</code>). Filtro completo: <code>%s</code>" % html.escape(filtros_dos_prints()["q3"][1]))}</div>
<p>O log de R1 na rodada 1 mostra a sequência: o vizinho fica inativo, R1 gera seu LSP e recalcula a tabela no mesmo instante.</p>
{pre(trecho_log)}
<p>A rota de R1 para R3 foi recalculada de <b>{n(min(rotas))} a {n(max(rotas))} s</b> depois da queda. Considerando a rede toda,
a convergência levou de <b>{n(s["total_s"]["min"])} a {n(s["total_s"]["max"])} s</b> (média de {n(s["total_s"]["media"])} s),
e <b>{n(fracao)}% desse tempo foi detecção</b>. A inundação e o recálculo somaram só {n(s["inundacao_e_recalculo_ms"]["min"], 0)}
a {n(s["inundacao_e_recalculo_ms"]["max"], 0)} ms. Mesmo essa parte vem principalmente de R1, R3 e R4 não detectarem a queda
no mesmo instante (diferença de {n(s["diferenca_entre_detectores_ms"]["min"], 0)} a {n(s["diferenca_entre_detectores_ms"]["max"], 0)} ms),
porque cada um verifica seus temporizadores em um ciclo próprio de 0,5 s: a inundação de um LSP levou no
máximo {n(s["maior_inundacao_de_um_lsp_ms"]["max"], 2)} ms, e uma execução do Dijkstra nesta topologia, cerca de
{n(r["um_dijkstra_na_local5_us"], 0)} µs.</p>
<h3>Relação com os temporizadores do HELLO</h3>
<p>Um vizinho é declarado inativo 20 s depois do <b>último HELLO recebido</b>, e não 20 s depois da queda. Como os HELLOs saem a
cada 5 s, a queda acontece de 0 a 5 s depois do último deles, e o tempo de detecção fica entre <b>15 e 20 s</b>, mais até 0,5 s do
ciclo de verificação. A tabela mostra exatamente isso: quanto mais tarde a queda em relação ao HELLO, menor a detecção. Somando
as duas colunas, o intervalo entre o último HELLO e a detecção foi sempre de {n(s["primeira_deteccao_apos_ultimo_hello_s"]["min"], 2)}
a {n(s["primeira_deteccao_apos_ultimo_hello_s"]["max"], 2)} s.</p>
<p>Portanto, para convergir mais rápido, o parâmetro que importa é o temporizador do HELLO. Reduzi-lo detecta falhas antes, mas
aumenta o tráfego de controle e o risco de declarar inativo um vizinho vivo quando alguns HELLOs se perdem. Com HELLO a cada 5 s e
limite de 20 s, a perda de dois HELLOs seguidos não derruba o vizinho; com três, o HELLO seguinte chega justamente no limite.</p>"""


def q4():
    r = ler("q4_sequencia")
    assert r["lsp_antigo_ainda_na_lsdb_ao_reiniciar"] and r["reinicio_real_aceito"]
    assert r["lsps_baixos_descartados"] and r["seq_baixo_aceito_apos_envelhecer"]
    for seq in (0, 1, 2):
        assert [(p[1], p[2]) for p in quadros(r["captura"], 'udp contains "LSP:10.6.2.1:%d:"' % seq)] == [(2, 1)]
    lsp3 = quadros(r["captura"], 'udp contains "LSP:10.6.2.1:3:"')
    assert all(a[2] == b[1] for a, b in zip(lsp3, lsp3[1:]))
    caminho3 = " &rarr; ".join(["R2"] + ["R%d" % p[2] for p in lsp3])
    return f"""<h2 class="nova">5. Questão 4: números de sequência</h2>
<p>Na inundação, o mesmo LSP chega a um roteador por vários caminhos e em momentos diferentes. O número de sequência permite
decidir, só comparando dois inteiros, se o LSP recebido é <b>mais novo</b> que o guardado. Ele cumpre três funções:</p>
<ul><li><b>encerra a inundação:</b> uma cópia já conhecida é descartada e não é reenviada; sem isso, o LSP circularia para
sempre nos ciclos da rede;</li>
<li><b>impede que informação velha substitua a nova:</b> um LSP atrasado na rede não desfaz uma atualização mais recente;</li>
<li><b>permite a renovação:</b> o LSP periódico, mesmo sem mudança, tem número maior e por isso é aceito e reinicia o envelhecimento.</li></ul>
<h3>E se um roteador reiniciado voltasse a numerar a partir de 0?</h3>
<p>Os outros roteadores ainda guardariam o LSP antigo, com número maior, e pela regra 2 do recebimento <b>descartariam os LSPs novos</b>
dele como se fossem antigos. O roteador voltaria a funcionar, mas a rede continuaria usando a topologia velha. Testamos isso: com R2 fora
do ar, enviamos a R1, a partir do mesmo par (IP, porta) de R2, LSPs com seq 0, 1 e 2, como faria um roteador que recomeçasse do zero.</p>
{pre(r["log_do_r1_sobre_os_seq_baixos"])}
<p>Os três foram descartados, e a LSDB de R1 manteve o seq {r["seq_na_lsdb_depois_dos_lsps_baixos"]}. Como nosso seq parte do Unix time,
da ordem de 1,8 bilhão, um contador recomeçando do 0 não o alcançaria na prática. A informação só voltaria a ser aceita depois que o LSP
antigo <b>envelhecesse</b>, isto é, após 90 s sem renovação. Depois disso, um LSP com seq 3 foi aceito:</p>
{pre(r["log_do_r1_apos_90s"])}
<div class="bloco"><p>A Figura 4 confirma isso na captura: os LSPs com seq 0, 1 e 2 chegam a R1 e não são reenviados, enquanto o LSP
com seq 3, aceito depois do envelhecimento, é inundado pelo caminho {caminho3}.</p>
{print_wireshark("q4", 4, "Wireshark: LSPs com número de sequência baixo vindos do par de R2 (<code>q4_sequencia.pcapng</code>).")}</div>
<p>A especificação evita essa janela: o primeiro seq é o horário atual em segundos, maior que os números usados antes do reinício. Para
comprovar, reiniciamos R2 de verdade 2 s depois de derrubá-lo, com o LSP antigo (seq {r["seq_antigo_na_lsdb_do_r1"]}) ainda na LSDB de R1.
O primeiro LSP depois do reinício (seq {r["seq_apos_reinicio_real"]}) foi aceito de imediato:</p>
{pre(r["log_do_r1_sobre_o_reinicio"])}
<p>Essa solução supõe que o relógio da máquina não volte no tempo e que o roteador não gere, em média, mais de um LSP por segundo,
o que vale aqui: os LSPs só saem em mudanças de vizinhança e a cada 30 s.</p>"""


def q5():
    r = ler("q5_confiabilidade")
    assert r["recuperou"]
    perdidos = [" ".join(l.split()[1:]) for l in r["copias_perdidas_pelo_r1"]]
    seq_perdido = r["copias_perdidas_pelo_r1"][0].split()[-1].split(":")[2]
    quadros_perdidos = [p[0] for p in quadros(r["captura"], 'udp contains "LSP:10.6.5.1:%s"' % seq_perdido) if p[2] == 1]
    assert len(quadros_perdidos) == len(perdidos) == 2
    return f"""<h2 class="nova">6. Questão 5: confiabilidade</h2>
<p>Como o LSP vai por UDP e não tem confirmação, quem envia não sabe se ele chegou. A inundação já oferece alguma redundância,
porque em uma rede com ciclos o LSP chega por mais de um vizinho. Mas, se <b>todas as cópias</b> se perderem, o roteador fica com
a LSDB <b>desatualizada</b> e calcula rotas erradas, enquanto os demais seguem corretos. Reproduzimos o caso: derrubamos R4 e
fizemos R1 perder as duas cópias do LSP em que R5 informa ter perdido R4.</p>
{pre(perdidos)}
<div class="bloco"><p>A Figura 5 mostra as duas cópias chegando à porta de R1 (quadros {quadros_perdidos[0]} e {quadros_perdidos[1]}). Elas aparecem na captura porque a
perda foi simulada no recebimento, dentro de R1. As linhas seguintes são a renovação do mesmo LSP, {n(r["segundos_com_lsdb_desatualizada"], 2)} s depois.</p>
{print_wireshark("q5", 5, "Wireshark: o LSP de R5 perdido por R1 e a renovação que o corrige (<code>q5_confiabilidade.pcapng</code>).")}</div>
<div class="bloco"><p>R1 continuou acreditando que R5 alcança R4 e ficou com uma <b>rota fantasma</b> de custo 11, enquanto R3, consultado logo em seguida, já
não tinha rota para R4:</p>
<div class="lado"><div><div class="rot">Tabela de R1 (LSDB desatualizada)</div>{pre(r["tabela_r1_com_lsdb_desatualizada"])}</div>
<div><div class="rot">Tabela de R3 (correta)</div>{pre(r["tabela_r3_no_mesmo_momento"])}</div></div></div>
<p>Um <code>ping</code> de R1 para R4 nesse momento saiu pela rota fantasma e foi barrado pelo primeiro roteador já atualizado:</p>
{pre(r["ping_r1_para_r4_nesse_momento"])}
<h3>Qual mecanismo recupera a LSDB?</h3>
<p>A <b>renovação periódica</b>: a cada 30 s, todo roteador gera um novo LSP com seq maior, mesmo sem mudança. Esse LSP carrega o estado
atual completo dos vizinhos da origem, então basta recebê-lo para corrigir a informação perdida. No experimento, a renovação de
R5 chegou a R1 <b>{n(r["segundos_com_lsdb_desatualizada"], 2)} s</b> depois da perda (no pior caso, cerca de 30 s), e a rota fantasma sumiu:</p>
{pre(r["renovacao_do_r5"] + [r["lsp_que_recuperou"]])}
{pre(r["tabela_r1_depois"])}
<p>Dois mecanismos completam a recuperação. A <b>sincronização com novo vizinho</b> entrega toda a LSDB a um roteador que acaba de
entrar ou voltar, sem esperar as renovações. O <b>envelhecimento</b> de 90 s remove o LSP de quem saiu da rede e parou de renová-lo;
como são três períodos de renovação, a perda de uma renovação não remove um roteador vivo; com duas perdas seguidas, a próxima
renovação chega justamente no limite dos 90 s.</p>"""


def q6():
    r = ler("q6_ttl_laco")
    maior_inundacao = ler("q3_resumo")["resumo"]["maior_inundacao_de_um_lsp_ms"]["max"]
    antes = r["tabelas_antes"]
    durante = r["tabelas_durante_o_laco"]
    depois = r["tabelas_depois"]

    def rota(tabela):
        return next(l for l in tabela if l.startswith("10.6.1.0/24")).split()

    pedidos = [p for p in quadros(r["captura"], 'udp contains "ICMP:10.6.5.1:10.6.1.1"')
               if p[3].split(":")[4] == "1" and p[3].endswith(":8")]
    assert len(pedidos) == len(r["saltos_do_pedido"])
    saltos = [[q, "R%d &rarr; R%d" % (de, para), texto.split(":")[3]] for q, de, para, texto in pedidos]
    linhas_rota = [["R2", "%s (custo %s)" % tuple(rota(antes["R2"])[1:]), "<b>%s</b> (custo %s)" % tuple(rota(durante["R2"])[1:]),
                    "%s (custo %s)" % tuple(rota(depois["R2"])[1:])],
                   ["R3", "%s (custo %s)" % tuple(rota(antes["R3"])[1:]), "<b>%s</b> (custo %s)" % tuple(rota(durante["R3"])[1:]),
                    "%s (custo %s)" % tuple(rota(depois["R3"])[1:])]]
    return f"""<h2 class="nova">7. Questão 6: TTL</h2>
<p>Todos os roteadores calculam as rotas com o mesmo algoritmo, mas <b>não recebem as mudanças ao mesmo tempo</b>. Durante a
convergência, dois roteadores podem usar versões diferentes da LSDB e, com isso, escolher rotas incompatíveis. Se um aponta para o
outro, forma-se um <b>laço</b> que dura até a informação chegar a todos. O TTL garante que um pacote preso nesse laço seja descartado
em vez de circular e consumir banda indefinidamente.</p>
<h3>Situação reproduzida</h3>
<p>Antes da falha, R3 alcança R1 por R2 (2 + 1 = 3). Cortamos o <b>enlace R1-R2</b>. R2 detecta a falha e recalcula: seu novo caminho
até R1 passa por R3 (2 + 4 = 6). Enquanto R3 não receber o LSP novo de R2, continua achando que R2 alcança R1 com custo 1 e mantém a
rota por R2. Nesse intervalo, <b>R2 envia para R3 e R3 devolve para R2</b>. Em nossa rede de teste um LSP se propaga em menos de 1 ms (no máximo {n(maior_inundacao, 2)} ms
na Tabela 6), então <b>atrasamos de propósito</b> a chegada desse LSP a R3 para poder observar a janela.</p>
{tab(["Roteador", "Antes da falha", "Durante o laço", "Depois da convergência"], linhas_rota)}
<div class="leg">Tabela 7. Próximo salto para a rede <code>10.6.1.0/24</code> em R2 e R3.</div>
<div class="bloco"><p>Durante o laço, executamos <code>ping 10.6.1.1</code> em R5. A Figura 6 mostra o mesmo pedido indo e voltando entre R3
(porta 6003) e R2 (porta 6002). O quarto campo do conteúdo é o TTL, que cai 1 a cada salto, de 16 até 1. As duas últimas linhas são o ICMP tipo 11
gerado por R2, voltando para R5.</p>
{print_wireshark("q6", 6, "Wireshark: as %d transmissões do pedido de eco em laço e o ICMP tipo 11 (<code>q6_ttl_laco.pcapng</code>)." % len(saltos))}</div>
<p>R2 recebeu o pacote com TTL 1, decrementou para 0, descartou e enviou um ICMP tipo 11 para a origem. R5 exibiu:</p>
{pre(r["ping_r5_para_r1_durante"])}
<p>Quando o LSP atrasado chegou, R3 passou a usar o enlace direto para R1 (custo 4), o laço acabou e o mesmo comando funcionou:</p>
{pre(r["ping_r5_para_r1_depois"])}
<p>Sem o TTL, o pacote continuaria circulando entre R2 e R3 durante todo o intervalo. Em uma rede com tráfego real, vários pacotes
presos assim poderiam congestionar justamente o enlace por onde a atualização precisa passar.</p>"""


def conclusao():
    q2r = ler("q2_inundacao")["rodadas"]
    totais = sorted({x["transmissoes"] for x in q2r})
    faixa = str(totais[0]) if len(totais) == 1 else "%d a %d" % (totais[0], totais[-1])
    q3r = ler("q3_resumo")["resumo"]
    fracao = q3r["deteccao_s"]["media"] / q3r["total_s"]["media"] * 100
    return f"""<div class="bloco"><h2 class="nova">8. Conclusão</h2>
<p>Os experimentos confirmaram o funcionamento do roteador e as propriedades do estado de enlace. O Dijkstra executado passo a passo sobre a
LSDB real coincidiu com a tabela do programa. Uma única queda gerou poucos LSPs ({faixa} transmissões, com
4 cópias descartadas), sem a contagem até o infinito do vetor de distância. O tempo de convergência é dominado pela
detecção da falha ({n(fracao)}% do total), ou seja, pelos temporizadores do HELLO; a inundação e o recálculo somaram no máximo {n(q3r["inundacao_e_recalculo_ms"]["max"], 0)} ms.
Por fim, cada mecanismo da especificação tem uma função observável: o número de sequência encerra a inundação e rejeita informação
antiga, a renovação periódica recupera LSPs perdidos, o envelhecimento remove quem saiu da rede e o TTL elimina pacotes presos em
laços transitórios.</p></div>"""


def anexo():
    q2r = ler("q2_inundacao")
    filtros = "<code>%s</code>" % html.escape(q2r["filtro"])
    linhas = [["<code>q1_dijkstra</code>", "Q1", "Convergência inicial", '<code>udp contains "LSP"</code>'],
              ["<code>q2_inundacao</code>", "Q2", "Queda de R4", filtros],
              *[["<code>q2_repeticao_%d</code>" % x["rodada"], "Q2", "Repetição da queda de R4", "<code>%s</code>" % html.escape(x["filtro"])]
                for x in q2r["rodadas"][1:]],
              ["<code>q3_convergencia_1</code> a <code>5</code>", "Q3", "Queda de R2, 5 rodadas", '<code>udp contains "HELLO:10.6.2.1"</code> (último HELLO de R2)'],
              ["<code>q4_sequencia</code>", "Q4", "Reinício de R2 e LSPs com seq baixo", '<code>udp contains "LSP:10.6.2.1:0:"</code>'],
              ["<code>q5_confiabilidade</code>", "Q5", "LSP do R5 perdido em R1", '<code>udp contains "LSP:10.6.5.1"</code>'],
              ["<code>q6_ttl_laco</code>", "Q6", "Laço R2-R3 e TTL", '<code>udp contains "ICMP:10.6.5.1:10.6.1.1"</code>']]
    return f"""<h2 class="pagina">Anexo A. Capturas entregues</h2>
<p>Os arquivos <code>.pcapng</code> estão em <code>docs/relatorio/capturas/</code>. Basta abrir no Wireshark e aplicar o filtro de
exibição indicado. O conteúdo de cada pacote aparece em texto ASCII no painel de bytes. Os filtros exatos dos prints estão na barra verde de
cada figura (o da Figura 3, por ser longo, também está na legenda).</p>
{tab(["Captura", "Questão", "O que contém", "Filtro de exibição"], linhas)}
<p>Os logs de cada roteador e os números medidos estão em <code>docs/relatorio/evidencias/</code>. O comando
<code>python3 docs/relatorio/experimentos.py</code> refaz todos os experimentos.</p>"""


def numerar(entrada, saida, pasta):
    """Põe o número da página no rodapé (menos na capa) e os metadados do documento."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from pypdf import PdfReader, PdfWriter

    leitor = PdfReader(entrada)
    rodapes = os.path.join(pasta, "rodapes.pdf")
    with PdfPages(rodapes) as pdf:
        for i, pagina in enumerate(leitor.pages, start=1):
            figura = plt.figure(figsize=(float(pagina.mediabox.width) / 72, float(pagina.mediabox.height) / 72))
            if i > 1:
                figura.text(0.5, 0.032, str(i), ha="center", fontsize=9, color="#555555", family="serif")
            pdf.savefig(figura, transparent=True)
            plt.close(figura)
    numeros = PdfReader(rodapes)
    escritor = PdfWriter()
    for pagina, numero in zip(leitor.pages, numeros.pages):
        pagina.merge_page(numero)
        escritor.add_page(pagina)
    escritor.add_metadata({"/Title": "Roteador de estado de enlace sobre UDP - Relatorio",
                           "/Author": "Grupo 6: " + ", ".join(INTEGRANTES),
                           "/Subject": "Trabalho final de " + DISCIPLINA})
    with open(saida, "wb") as arquivo:
        escritor.write(arquivo)


def main():
    corpo = "".join([capa(), metodologia(), q1(), q2(), q3(), q4(), q5(), q6(), conclusao(), anexo()])
    corpo = re.sub(r'(<table>(?:(?!</table>).)*</table>)\s*(<div class="leg">.*?</div>)',
                   r'<div class="bloco">\1\2</div>', corpo, flags=re.S)
    corpo = re.sub(r'((?:<h[23][^>]*>(?:(?!</h[23]>).)*</h[23]>\s*)?<p>(?:(?!</p>).)*</p>)\s*(<pre>.*?</pre>)',
                   r'<div class="bloco">\1\2</div>', corpo, flags=re.S)
    corpo = re.sub(r'(<h[23][^>]*>(?:(?!</h[23]>).)*</h[23]>)\s*(<p>(?:(?!</p>).)*</p>)',
                   r'<div class="bloco">\1\2</div>', corpo, flags=re.S)
    pagina = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
              "<title>Roteador de estado de enlace sobre UDP - Relatorio - Grupo 6</title><style>"
              + CSS + "</style></head><body>" + corpo + "</body></html>")
    saida = SAIDA
    pasta = tempfile.mkdtemp(prefix="relatorio_")
    try:
        entrada = os.path.join(pasta, "relatorio.html")
        with open(entrada, "w", encoding="utf-8") as arquivo:
            arquivo.write(pagina)
        impressor = os.path.join(pasta, "imprime")
        subprocess.run(["swiftc", "-O", os.path.join(AQUI, "imprime_pdf.swift"), "-o", impressor], check=True)
        bruto = os.path.join(pasta, "bruto.pdf")
        subprocess.run([impressor, entrada, bruto], check=True, timeout=60, stdout=subprocess.DEVNULL)
        numerar(bruto, saida, pasta)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    print("Gerado:", os.path.relpath(saida))


if __name__ == "__main__":
    main()
