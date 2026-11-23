"""Gera a figura da topologia local5 usada no relatório (figuras/topologia_local5.png).

As arestas e os custos são lidos de configs/local5, para a figura nunca divergir das configurações.
Só este script usa matplotlib; o roteador continua apenas com a biblioteca padrão.

Uso, da raiz do repositório: python3 docs/relatorio/figura_topologia.py
"""

import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))

POSICOES = {1: (0.0, 1.0), 2: (2.2, 2.0), 3: (2.2, 0.0), 4: (4.6, 2.0), 5: (4.6, 0.0)}
COR_NO, COR_TEXTO, COR_ARESTA = "#1F4E79", "#FFFFFF", "#5B6770"


def ler_arestas():
    """{(a, b): custo}, com a < b, a partir dos arquivos configs/local5/r*.conf."""
    arestas = {}
    for caminho in sorted(glob.glob(os.path.join(RAIZ, "configs", "local5", "r*.conf"))):
        n = int(os.path.basename(caminho)[1])
        with open(caminho, encoding="utf-8") as arquivo:
            for linha in arquivo:
                partes = linha.split("#")[0].split()
                if partes and partes[0] == "vizinho":
                    outro = int(partes[2]) - 6000
                    arestas[(min(n, outro), max(n, outro))] = int(partes[3])
    return arestas


def main():
    fig, eixo = plt.subplots(figsize=(8.2, 4.4), dpi=200)
    for (a, b), custo in ler_arestas().items():
        (xa, ya), (xb, yb) = POSICOES[a], POSICOES[b]
        eixo.plot([xa, xb], [ya, yb], color=COR_ARESTA, linewidth=2, zorder=1)
        eixo.text((xa + xb) / 2, (ya + yb) / 2, str(custo), ha="center", va="center", fontsize=12,
                  fontweight="bold", zorder=3,
                  bbox=dict(boxstyle="circle,pad=0.25", facecolor="white", edgecolor=COR_ARESTA))
    for n, (x, y) in POSICOES.items():
        eixo.scatter([x], [y], s=1500, color=COR_NO, zorder=2)
        eixo.text(x, y, "R%d" % n, ha="center", va="center", color=COR_TEXTO, fontsize=13,
                  fontweight="bold", zorder=4)
        abaixo = y <= 0.0 or (n == 1)
        eixo.text(x, y + (-0.42 if abaixo else 0.42), "10.6.%d.1\nUDP %d" % (n, 6000 + n), ha="center",
                  va="top" if abaixo else "bottom", fontsize=8.5, color="#333333")
    eixo.set_xlim(-0.8, 5.4)
    eixo.set_ylim(-0.95, 2.95)
    eixo.set_aspect("equal")
    eixo.axis("off")
    pasta = os.path.join(AQUI, "figuras")
    os.makedirs(pasta, exist_ok=True)
    fig.savefig(os.path.join(pasta, "topologia_local5.png"), bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    main()
