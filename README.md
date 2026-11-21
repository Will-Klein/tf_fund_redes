# Roteador de estado de enlace sobre UDP — Grupo 6

Trabalho final de Fundamentos de Redes: roteador de estado de enlace (inspirado no OSPF) executando
como aplicação sobre UDP. Descobre vizinhos com HELLO, inunda LSPs, monta a LSDB, calcula a tabela
com Dijkstra e encaminha DADOS/ICMP com TTL (`ping`, tempo excedido, destino inalcançável).

Integrantes: William, Frederico e Gustavo. Endereços virtuais `10.6.R.1` (R1 William,
R2 Frederico, R3 Gustavo).

> **Estado:** em desenvolvimento (falta o `forwarding.py`). Andamento em `docs/PROGRESS.md`.

## Requisitos

- Python 3.8 ou mais novo, só a biblioteca padrão (nada para instalar).
- No **Windows** (é o caso da VM da VDI da PUCRS), use `py` no lugar de `python3` em todos os
  comandos abaixo; caminhos com `/` funcionam igual (ex.: `py router.py configs/grupo/r1.conf`).

## Execução

```bash
python3 router.py <arquivo de configuração>
```

Exemplo, 5 roteadores na mesma máquina (um terminal para cada):

```bash
python3 router.py configs/local5/r1.conf
```

Comandos digitados no terminal do roteador (`<destino>` é um endereço virtual):

| Comando | Ação |
|---|---|
| `tabela` | tabela de roteamento (rede, próximo salto, custo) |
| `lsdb` | LSDB (origem, número de sequência, vizinhos e custos) |
| `vizinhos` | vizinhos ativos (endereço virtual, IP real, porta) |
| `msg <destino> <texto>` | envia um pacote de dados |
| `ping <destino> [TTL]` | pedido de eco (TTL padrão 16); mostra a resposta, quem enviou e o RTT, ou timeout após 2 s |
| `sair` | encerra o roteador |

Os logs ficam no terminal e em `logs/<endereço virtual>.log`.

## Formato do arquivo de configuração

Texto, uma diretiva por linha; `#` inicia um comentário; linhas vazias são ignoradas.

```
endereco 10.6.1.1               # endereço virtual do roteador (10.G.R.1)
porta 6000                      # porta UDP local (opcional; padrão 6000)
vizinho 192.168.0.12 6000 1     # vizinho <IP real> <porta UDP> <custo inteiro positivo>
vizinho 192.168.0.13 6000 7
```

- O IP do vizinho deve ser o IP real de onde os pacotes dele chegam (não use nome de máquina).
- Um enlace só existe se os **dois** lados listarem um ao outro, com o **mesmo** custo.
- Para ligar à rede de outro grupo, basta uma linha `vizinho` a mais em cada lado.

Configurações prontas:
- `configs/local5/` — 5 roteadores em `127.0.0.1`, portas 6001–6005 (testes e relatório).
- `configs/grupo/` — rede do grupo (3 roteadores) para a apresentação; troque `IP_Rn` pelo IP real de cada VM.
- `configs/teste_vdi/` — só R1 e R3, para o teste rápido entre duas VMs (`docs/TESTE_VDI.md`).

## Testes

Testes unitários (rápidos):

```bash
python3 -m unittest discover tests
```

Teste de integração (sobe os 5 roteadores da `local5` nas portas 6001–6005; leva ~1 minuto):

```bash
python3 tests/integration_local.py
```
