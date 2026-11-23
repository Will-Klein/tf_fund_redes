"""Monta docs/relatorio/RESULTADOS.md a partir de evidencias/*/resultado.json.

Assim nenhum número do relatório é copiado à mão: se um experimento for refeito, basta rodar de novo.
Uso, da raiz do repositório: python3 docs/relatorio/gera_resultados.py
"""

import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))


def ler(nome):
    with open(os.path.join(AQUI, "evidencias", nome, "resultado.json"), encoding="utf-8") as arquivo:
        return json.load(arquivo)


def bloco(linhas):
    return "```\n" + "\n".join(linhas) + "\n```\n"


def tabela(cabecalho, linhas):
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    for linha in linhas:
        saida.append("| " + " | ".join(str(c) for c in linha) + " |")
    return "\n".join(saida) + "\n"


def q1():
    r = ler("q1_dijkstra")
    nos = ["R2", "R3", "R4", "R5"]
    linhas = [[i["passo"], ", ".join(i["N"])] + [i["D"][n] for n in nos] for i in r["iteracoes"]]
    return ("## Q1. Dijkstra (R1)\n\nCaptura: `%s`\n\nLSDB do R1 (comando `lsdb`):\n\n%s\n"
            "Iterações (`custo,predecessor`):\n\n%s\nTabela exibida pelo programa (`tabela`):\n\n%s\n"
            "**O resultado passo a passo é igual à tabela do programa: %s.**\n"
            % (r["captura"], bloco(r["lsdb_r1"]),
               tabela(["Passo", "N'", "R2", "R3", "R4", "R5"], linhas), bloco(r["tabela_r1"]),
               "sim" if r["igual_ao_programa"] else "NAO"))


def q2():
    r = ler("q2_inundacao")
    linhas = [[nome, d["seq"], d["transmissoes"], d["aceitos_como_novos"], d["descartados_copia"],
               d["enviados_ao_R4_morto"], " ".join(d["caminho"])] for nome, d in r["por_lsp"].items()]
    t = r["total"]
    linhas.append(["**Total**", "", t["transmissoes"], t["aceitos_como_novos"], t["descartados_copia"],
                   t["enviados_ao_R4_morto"], ""])
    dv = [["%s, infinito = %d" % ("poison reverse" if d["poison_reverse"] else "sem proteção", d["infinito"]),
           d["rodadas"], d["mensagens"]] for d in r["vetor_distancia"]]
    rodadas = [[x["rodada"], x["queda_apos_a_partida_s"], x["transmissoes"], x["aceitos_como_novos"], x["descartados_copia"],
                x["enviados_ao_R4_morto"], x["lsps_extras_na_janela"], x["captura"]] for x in r["rodadas"]]
    return ("## Q2. Inundação (queda do R4)\n\nCaptura: `%s`\n\n"
            "A queda gerou %d LSPs novos (R2 e R5, os vizinhos do R4), %.3f s depois da queda.\n\n%s\n"
            "Repetições da mesma queda:\n\n%s\n"
            "Vetor de distância na mesma queda (**modelo** em rodadas síncronas, com atualização disparada; "
            "não é medição):\n\n%s"
            % (r["captura"], r["lsps_gerados_pela_mudanca"], r["segundos_entre_queda_e_primeiro_lsp"],
               tabela(["LSP de", "seq", "Transmissões", "Aceitos", "Cópias descartadas", "Ao R4 morto", "Caminho"],
                      linhas),
               tabela(["Rodada", "Queda após a partida (s)", "Transmissões", "Aceitas", "Cópias", "Ao R4 morto", "Outros LSPs na janela", "Captura"], rodadas),
               tabela(["Variante", "Rodadas", "Mensagens"], dv)))


def q3():
    r = ler("q3_resumo")
    linhas = [[m["rodada"], m["queda_apos_ultimo_hello_s"], m["deteccao_s"], m["inundacao_e_recalculo_ms"],
               m["maior_inundacao_de_um_lsp_ms"], m["total_s"]] for m in r["medidas"]]
    nomes = {"deteccao_s": "Detecção (s)", "inundacao_e_recalculo_ms": "Inundação + recálculo (ms)",
             "maior_inundacao_de_um_lsp_ms": "Maior inundação de um LSP (ms)", "total_s": "Total (s)",
             "primeira_deteccao_apos_ultimo_hello_s": "Último HELLO até a detecção (s)",
             "diferenca_entre_detectores_ms": "Diferença entre R1, R3 e R4 detectarem (ms)"}
    resumo = [[nomes[c], v["min"], v["media"], v["max"]] for c, v in r["resumo"].items()]
    return ("## Q3. Convergência (queda do R2, no caminho R1-R2-R3)\n\nCapturas: `capturas/q3_convergencia_1..5.pcapng`\n\n%s\n%s\n"
            "Uma execução do Dijkstra na `local5` leva cerca de %.1f µs.\n"
            % (tabela(["Rodada", "Queda após o último HELLO (s)", "Detecção (s)", "Inundação + recálculo (ms)",
                       "Maior inundação de um LSP (ms)", "Total (s)"], linhas),
               tabela(["Medida", "Mín.", "Média", "Máx."], resumo), r["um_dijkstra_na_local5_us"]))


def q4():
    r = ler("q4_sequencia")
    return ("## Q4. Números de sequência\n\nCaptura: `%s`\n\n"
            "LSPs com **seq 0, 1 e 2** vindos do par do R2 (simulam um reinício que recomeça do 0); a LSDB tinha o seq `%d`:\n\n%s\n"
            "Só depois dos 90 s de envelhecimento um seq baixo volta a ser aceito:\n\n%s\n"
            "Reinício real do R2 com o LSP antigo (seq `%d`) ainda na LSDB do R1; o 1º seq é o Unix time, `%d`:\n\n%s"
            % (r["captura"], r["seq_guardado_antes_dos_lsps_baixos"], bloco(r["log_do_r1_sobre_os_seq_baixos"]),
               bloco(r["log_do_r1_apos_90s"]), r["seq_antigo_na_lsdb_do_r1"], r["seq_apos_reinicio_real"],
               bloco(r["log_do_r1_sobre_o_reinicio"])))


def q5():
    r = ler("q5_confiabilidade")
    return ("## Q5. Confiabilidade (LSP perdido)\n\nCaptura: `%s`\n\n"
            "Depois da queda do R4, o R1 perdeu **todas as cópias** de um LSP do R5 (falha injetada na recepção):\n\n%s\n"
            "LSDB do R1 desatualizada (o R5 ainda lista o R4):\n\n%s\nTabela do R1 com rota fantasma para o R4:\n\n%s\n"
            "Tabela do R3 no mesmo momento (correta):\n\n%s\nPing do R1 para o R4 nesse momento:\n\n%s\n"
            "Recuperação pela renovação periódica do R5, %.3f s depois da perda (nesta execução; o pior caso é 30 s):\n\n%s\n"
            "Tabela do R1 depois:\n\n%s"
            % (r["captura"], bloco(r["copias_perdidas_pelo_r1"]), bloco(r["lsdb_r1_desatualizada"]),
               bloco(r["tabela_r1_com_lsdb_desatualizada"]), bloco(r["tabela_r3_no_mesmo_momento"]),
               bloco(r["ping_r1_para_r4_nesse_momento"]), r["segundos_com_lsdb_desatualizada"],
               bloco(r["renovacao_do_r5"] + [r["lsp_que_recuperou"]]), bloco(r["tabela_r1_depois"])))


def q6():
    r = ler("q6_ttl_laco")
    saltos = [[i + 1, s["enlace"], s["ttl"]] for i, s in enumerate(r["saltos_do_pedido"])]
    return ("## Q6. TTL e laço durante a convergência\n\nCaptura: `%s`\n\n"
            "O enlace R1-R2 foi cortado e o LSP novo do R2 foi **atrasado de propósito** até o R3 "
            "(sem isso, a janela dura menos de 1 ms). Tabelas durante o laço:\n\nR2:\n\n%s\nR3:\n\n%s\n"
            "Para a rede `10.6.1.0/24`, o R2 aponta para o R3 e o R3 aponta para o R2. "
            "Ping do R5 para o R1 nesse momento:\n\n%s\nCaminho do pedido, na captura (TTL com que saiu em cada salto):\n\n%s\n"
            "Depois que o LSP passou, o mesmo ping:\n\n%s"
            % (r["captura"], bloco(r["tabelas_durante_o_laco"]["R2"]), bloco(r["tabelas_durante_o_laco"]["R3"]),
               bloco(r["ping_r5_para_r1_durante"]), tabela(["Salto", "Enlace", "TTL"], saltos),
               bloco(r["ping_r5_para_r1_depois"])))


def main():
    partes = ["# Resultados dos experimentos\n\n"
              "*Arquivo gerado por `gera_resultados.py` a partir das medições em `evidencias/`. Não editar à mão.*\n\n"
              "Como foi medido: 5 processos reais do roteador (topologia `local5`, `configs/local5`) numa só máquina, "
              "em `127.0.0.1`, portas 6001 a 6005, como o enunciado permite. Captura na loopback com o Wireshark "
              "(`dumpcap`). Para refazer: `python3 docs/relatorio/experimentos.py`.\n\n"
              "![Topologia local5](figuras/topologia_local5.png)\n",
              q1(), q2(), q3(), q4(), q5(), q6()]
    with open(os.path.join(AQUI, "RESULTADOS.md"), "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(partes))


if __name__ == "__main__":
    main()
