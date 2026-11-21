# IMPLEMENTATION_PLAN — Plano técnico detalhado

> Status: **aprovado por William em 2026-11-19; F0 concluída** (o resto ainda não foi implementado) (revisado em 2026-11-19 com G = 6,
> ambiente VDI; revisão geral contra o enunciado feita na mesma data, ver `DECISIONS.md` D32–D36).
> 2026-11-20: Leonardo saiu, grupo virou trio; donos e topologia `grupo` atualizados (D41, D42).
> IDs de requisito (RFxx) definidos em [`PROJECT_CONTEXT.md §2`](PROJECT_CONTEXT.md).
> Decisões/interpretações (Dxx) em [`DECISIONS.md`](DECISIONS.md).

---

## 1. Princípios

1. **Fidelidade ao enunciado** acima de tudo: formatos literais, regras na ordem do texto.
2. **Simplicidade explicável**: Python + biblioteca padrão, funções curtas, comentários em português
   citando a regra do enunciado. Nada de frameworks, asyncio, classes abstratas ou plugins.
3. **Lógica pura separada de E/S**: parsing, config e Dijkstra são funções puras (fáceis de testar
   e de explicar). O Router recebe o socket e o relógio por injeção simples para ser testável.
4. **Um dono por arquivo**.

---

## 2. Arquitetura

### 2.1 Threads e concorrência (D02)

```
            ┌──────────────────────────── Router (estado + 1 lock) ───────────────────────────┐
 stdin ──►  │ Thread principal: cli.py ── tabela/lsdb/vizinhos/msg/ping                       │
            │ Thread recepção: recvfrom() ─► filtro de vizinho ─► packets.parse ─► despacho   │
 UDP  ◄──►  │      HELLO → vizinhança   LSP → LSDB/inundação   DADOS/ICMP → forwarding        │
            │ Thread temporizador (tick 0,5 s): HELLO 5 s · LSP 30 s · inativo 20 s · aging 90 s│
            └──────────────────────────────────────────────────────────────────────────────────┘
                          │ log.py → terminal + logs/<endereço>.log
```

- Um único `threading.RLock` protege vizinhos, LSDB, tabela e seq. Todo handler roda inteiro
  dentro do lock (inclusive o `sendto`, que em UDP não bloqueia na prática).
- `ping`: a CLI registra o pedido pendente, envia, e espera num `threading.Event` **fora do lock**
  por até 2 s; a thread de recepção sinaliza o Event ao receber ICMP 0/11/3 com aquele id.
- Threads de recepção e temporizador são `daemon=True`; `sair` ou Ctrl+C encerram o programa.

### 2.2 Estado do Router (`router.py`)

```python
self.address        # '10.G.R.1'
self.port           # porta UDP
self.sock           # socket UDP único, bind(('0.0.0.0', port))  (D04)
self.neighbors      # {(ip, porta): Vizinho}
#   Vizinho: cost (config), virtual (do HELLO ou None), active (bool), last_hello (monotonic)
self.lsdb           # {origem: EntradaLSDB}
#   EntradaLSDB: seq, neighbors {end_virtual: custo}, received_at (monotonic; próprio: None)
self.seq            # último nº de sequência próprio usado (None até o 1º LSP, D30)
self.routes         # {roteador_destino: (proximo_salto, custo)}  (saída do Dijkstra)
self.table          # {'10.G.R.0/24': (proximo_salto, custo)}    (derivada de routes)
```

### 2.3 Fluxos principais

**Recepção de datagrama** (`handle_datagram(data, peer)`):
1. `peer` ∉ `neighbors` → descarta (log DESCARTE) — RF03.
2. `packets.parse(data)`; `MalformedPacket` → descarta (log DESCARTE) — RF04.
3. Despacha por tipo: `Hello` → `handle_hello`; `Lsp` → `handle_lsp`; `Dados`/`Icmp` → `forwarder.handle`.

**HELLO** (`handle_hello(pkt, peer)`) — RF06, RF08, RF13:
- Atualiza `last_hello`. Se estava inativo: marca ativo, associa `virtual`, log VIZINHO ATIVO,
  `generate_own_lsp()` (envia a todos os ativos, incluindo o novo) e depois envia **ao novo vizinho**
  uma cópia de **todos** os LSPs da LSDB, inclusive o próprio (sincronização, D31); log
  `LSP sincronização: N LSPs enviados a <vizinho>` (evidência do critério 2).
- Se já ativo mas o endereço virtual mudou: atualiza e gera novo LSP (D21).

**Temporizador** (`tick()`, a cada 0,5 s) — RF05, RF07, RF09, RF14:
- HELLO: o 1º sai **na partida**; depois, a cada 5 s → `HELLO:<end>` a **todos os configurados**.
- Vizinho ativo com `agora - last_hello >= 20` → inativo, log, `generate_own_lsp()`.
- Renovação: a cada 30 s em **período fixo** contado desde a partida (independe dos LSPs gerados
  por mudança de vizinho) → `generate_own_lsp()` (D32).
- LSP alheio com `agora - received_at >= 90` → remove, log `LSP envelhecido`, `recompute()`.

**Geração de LSP próprio** (`generate_own_lsp(motivo)`) — RF09–RF11, D30, D32:
- Gatilhos: vizinho ficou ativo/inativo, ou a renovação periódica de 30 s. **Não** há LSP na partida (D30).
- 1º LSP: `seq = int(time.time())`; depois `seq = seq + 1`.
- Lista = vizinhos **ativos** `{virtual: cost}`; grava na LSDB; envia a todos os ativos; `recompute()`.

**Recebimento de LSP** (`handle_lsp(pkt, peer)`) — RF12, D05, D06, D22:
1. `pkt.origin == self.address` → descarta (log `LSP descartado: própria origem`).
2. LSDB tem `seq >= pkt.seq` → descarta (log `LSP descartado: cópia/antigo`).
3. Senão: grava (com `received_at = agora`), log `LSP novo`, reenvia a todos os ativos exceto `peer`
   o LSP **re-codificado** com `packets.encode(pkt)` — mesma origem, mesmo seq, mesma lista (D35) —
   e `recompute()`.

Todo LSP recebido gera exatamente uma dessas 3 linhas de log; somando as 3 nos logs de todos os
roteadores, obtém-se o total de LSPs que circularam (Q2 do relatório).

**Recálculo** (`recompute(motivo)`) — RF15–RF17:
- Monta `grafo = {origem: entrada.neighbors}` → `dijkstra.dijkstra(grafo, self.address)` →
  `table[network_of(dest)] = (prox, custo)`; log TABELA em 1 linha e a tabela inteira só se mudou (D29).

**Encaminhamento** (`forwarding.py`) — RF18–RF21: ver §4.5.

**Robustez** (RF04 "sem derrubar o roteador", D33): o corpo do laço de recepção e o do
temporizador ficam dentro de `try/except Exception` que registra `ERRO ...` no log e continua;
`send()` captura `OSError`. Assim, nenhum pacote inesperado nem erro de rede (ex.:
`ConnectionResetError` do Windows no plano B) mata uma thread.

---

## 3. Formato do arquivo de configuração (D03)

Texto simples, uma diretiva por linha, `#` inicia comentário, linhas vazias ignoradas.

```
# Roteador 1 do grupo 6 (William)
endereco 10.6.1.1
porta 6000                      # opcional; padrão 6000
# vizinho <IP real> <porta UDP> <custo>
vizinho 192.168.0.12 6000 1     # R2 (Frederico)
vizinho 192.168.0.13 6000 5     # R3 (Gustavo)
```

Validação (erro claro com nº da linha, e o programa não inicia): `endereco` obrigatório e IPv4
válido (aviso se não seguir `10.G.R.1`); porta 1–65535; IP do vizinho IPv4 literal; custo inteiro
> 0; par (IP, porta) duplicado é erro. Uso: `python3 router.py configs/grupo/r1.conf`.

**Interoperabilidade** = acrescentar uma linha `vizinho <IP do outro grupo> <porta> <custo>` (com o
mesmo custo do lado de lá).

---

## 4. Módulos, interfaces e funcionalidades

Para cada item: **o que** · **requisito** · **teste**.

### 4.1 `packets.py` — William (primeira entrega, todos dependem)

```python
Hello = namedtuple('Hello', 'addr')
Lsp   = namedtuple('Lsp',   'origin seq neighbors')      # neighbors: dict {end: custo}
Dados = namedtuple('Dados', 'src dst ttl id msg')
Icmp  = namedtuple('Icmp',  'src dst ttl id type')
class MalformedPacket(Exception): ...
def parse(data: bytes)            # -> Hello | Lsp | Dados | Icmp, ou levanta MalformedPacket
def encode(pkt) -> bytes
def is_virtual_addr(s) -> bool    # IPv4 com 4 octetos 0..255
def network_of(addr) -> str       # '10.6.2.1' -> '10.6.2.0/24'
def same_network(a, b) -> bool    # 3 primeiros octetos iguais
def valid_text(msg) -> bool       # só caracteres ASCII, sem ':' (D13)
```

- **O que:** formatação exata e parsing estrito: decodificação ASCII estrita; `split(':')` com nº
  exato de campos (HELLO 2, LSP 4, DADOS 6, ICMP 6); numéricos só com dígitos; endereços válidos;
  custo > 0; tipo ICMP ∈ {0, 3, 8, 11}. Tolerâncias (D12): `\n`/`\r\n` no fim do datagrama; itens
  vazios na lista do LSP (ex.: `;` final). `encode` nunca gera essas sobras.
- **Requisitos:** RNF01, RF04, RF11 (lista vazia), formatos de todos os pacotes.
- **Testes:** `tests/test_packets.py` — os 5 exemplos literais do enunciado (ida e volta);
  `LSP:10.3.1.1:1767712001:` (lista vazia); malformados: tipo desconhecido, campos a mais/menos,
  TTL/seq/id/custo não numérico, custo 0, endereço inválido, mensagem com acento, bytes não ASCII.

### 4.2 `config.py` — William

```python
NeighborConf = namedtuple('NeighborConf', 'ip port cost')
Config       = namedtuple('Config', 'address port neighbors')
class ConfigError(Exception): ...
def load_config(path) -> Config
```
- **Requisito:** RF01. **Testes:** `tests/test_config.py` — arquivo válido, porta padrão 6000,
  comentários, cada erro de validação da §3.

### 4.3 `dijkstra.py` — Frederico

```python
def dijkstra(graph, source):
    """graph: {nó: {vizinho: custo}}  ->  {destino: (proximo_salto, custo)}  (sem o próprio source)."""
```
- **O que:** Dijkstra com `heapq`; cada nó carrega o primeiro salto do caminho; arestas **dirigidas**
  exatamente como estão nos LSPs (D07); nós que só aparecem como vizinho em algum LSP também são
  destinos. Empate: qualquer um (determinístico por ordem do heap).
- **Requisitos:** RF15, RF16. **Proibido:** networkx, scipy etc.
- **Contrato extra:** se `source` ainda não estiver no grafo (LSPs recebidos antes do próprio, D05),
  devolve `{}` sem erro.
- **Testes:** `tests/test_dijkstra.py` — topologia `local5` com resultado calculado à mão; source fora do grafo; nó
  inalcançável; empate; aresta só de ida; grafo só com o source; caminho alternativo após remover nó.

### 4.4 `router.py` — P1 (William)

```python
class Router:
    def __init__(self, config, logger, sock=None, clock=time.monotonic)
    def start(self)                       # cria socket (se None) e as threads
    def handle_datagram(self, data, peer) # ponto único de entrada (testável sem rede)
    def tick(self)                        # chamado pelo temporizador (testável)
    def route_for(self, dst)              # -> (proximo_salto, (ip, porta)) ou None
    def is_local(self, addr) -> bool      # addr ∈ 10.G.R.0/24 próprio
    def send(self, data, peer)
    # leitura para a CLI (cópias sob lock):
    def get_table(self)            # {'10.6.2.0/24': ('10.6.2.1', 1)}  rede: (próximo salto, custo)
    def get_lsdb(self)             # {'10.6.1.1': (seq, {'10.6.2.1': 1})}  origem: (seq, {vizinho: custo})
    def get_active_neighbors(self) # [('10.6.2.1', '192.168.0.12', 6000)]  (virtual, IP real, porta)
```

| Funcionalidade | Requisito | Teste |
|---|---|---|
| Socket único, bind `0.0.0.0:porta` | RF02 | integração (porta de origem = porta do roteador, visto no Wireshark) |
| Filtro de par desconhecido | RF03 | unit: datagrama de par não configurado não muda estado |
| HELLO a cada 5 s a todos os configurados | RF05 | unit com relógio falso: `tick()` em t=0,5,10 envia HELLO |
| Ativo no 1º HELLO + associação virtual↔(IP, porta) | RF06 | unit |
| Inativo após 20 s | RF07 | unit: relógio avança 20,5 s → inativo + novo LSP |
| LSP imediato a cada mudança | RF08, RF09 | unit: seq incrementa e LSP enviado aos ativos |
| Seq inicial = Unix time, +1, inalterado ao reenviar | RF10 | unit: reenvio é byte a byte igual ao recebido |
| Lista só de ativos; vazia `LSP:o:s:` | RF11 | unit |
| Regras de recebimento 1–3 e inundação exceto V | RF12 | unit: própria origem / seq igual / seq menor / seq maior |
| Sincronização com novo vizinho | RF13 | unit: novo ativo recebe todos os LSPs da LSDB |
| Envelhecimento 90 s | RF14 | unit: relógio avança 90,5 s → removido + recálculo; LSP próprio nunca envelhece |
| Recálculo quando a LSDB muda | RF17 | unit: tabela atualizada após cada caso acima |
| Exceção num handler não derruba a thread | RF04, D33 | unit: datagrama que provoca erro → log ERRO e o próximo datagrama é processado |

### 4.5 `forwarding.py` — Frederico

```python
class Forwarder:
    def __init__(self, router)
    def send_data(self, dst, text) -> str        # comando msg; retorna texto para o usuário
    def ping(self, dst, ttl=16) -> str           # bloqueia até resposta ou 2 s
    def handle(self, pkt, peer)                  # Dados/Icmp vindos da rede
```

| Funcionalidade | Requisito | Teste |
|---|---|---|
| Originar: sem rota → "destino inalcançável" sem enviar; com rota → envia com TTL inicial | RF18 | unit com Router falso |
| Originar para a própria rede: passa o pacote direto à função de recebimento (entrega local, D09) | RF19 | unit: `ping` ao próprio endereço responde eco |
| Destino local: DADOS exibe origem/destino/mensagem | RF19 | unit (inclui `10.G.R.50`, qualquer host da /24) |
| ICMP 8 local → ICMP 0, mesmo id, origem = destino do pedido, TTL 16 | RF19 | unit |
| ICMP 0/11/3 local → resultado ao usuário / acorda o ping pendente | RF19, RF23 | unit |
| Trânsito: TTL−1; chegou a 0 → descarta + ICMP 11 à origem | RF20, RF21 | unit (TTL 1 chega → gera 11) |
| Trânsito sem rota → descarta + ICMP 3 à origem | RF20, RF21 | unit |
| Ordem do enunciado: TTL antes da rota (TTL 1 **e** sem rota → gera 11, não 3) | RF20 | unit |
| Pacote gerado pelo próprio roteador (eco 0, erro 11/3) sem rota de volta → não envia, só log | RF18, D11 | unit |
| Encaminha com novo TTL ao (IP, porta) do próximo salto + log | RF20, RF24 | unit |
| Nunca erro em resposta a erro (11/3 não geram 11/3) | RF21 | unit (ICMP 11 com TTL 1 em trânsito é só descartado) |
| `ping`: id por contador, RTT em ms, timeout 2 s | RF23 | unit (timeout) + integração |

### 4.6 `cli.py` — P2 (William)

Comandos `tabela`, `lsdb`, `vizinhos`, `msg <destino> <texto>`, `ping <destino> [TTL]` (RF23) +
`sair` (D20; comando desconhecido mostra a lista de comandos válidos). Em `msg`, o texto é todo o
resto da linha (pode ter espaços). Validações antes de enviar: destino é endereço virtual válido;
TTL inteiro ≥ 1; texto válido (`valid_text`). Colunas exigidas pelo enunciado:
`tabela` = rede, próximo salto, custo · `lsdb` = origem, nº de sequência, vizinhos e custos ·
`vizinhos` = só os **ativos**: endereço virtual, IP real, porta. Exemplo (R1 da topologia `grupo`, trio):

```
> tabela
Rede destino     Próximo salto   Custo
10.6.2.0/24      10.6.2.1        1
10.6.3.0/24      10.6.2.1        3
> lsdb
Origem      Seq          Vizinhos (custo)
10.6.1.1    1795111000   10.6.2.1=1, 10.6.3.1=5
10.6.2.1    1795111003   10.6.1.1=1, 10.6.3.1=2
10.6.3.1    1795111002   10.6.1.1=5, 10.6.2.1=2
> vizinhos
Endereço virtual   IP real          Porta
10.6.2.1           192.168.0.12     6000
10.6.3.1           192.168.0.13     6000
> ping 10.6.3.1 1
Tempo excedido informado por 10.6.2.1 (id=4) RTT=0.84 ms
> ping 10.9.9.1
Destino inalcancavel: sem rota para 10.9.9.0/24 (nada foi enviado)
```

### 4.7 `log.py` — P2 (William)

Textos de log e de tela sempre ASCII, sem acentos (D39). `Logger(path)`; `log(categoria, texto, terminal=True)` → `2026-11-19 16:01:02.123 [CATEGORIA] texto`,
escrito sempre com `flush` imediato no arquivo `logs/<endereço>.log` e, se `terminal=True`, também no
terminal (`terminal=False` só para HELLO, D34). Thread-safe.

| Categoria | Evento | Exigido? |
|---|---|---|
| VIZINHO | ficou ativo / inativo | RF24 |
| LSP | novo recebido (origem, seq, de quem); gerado (motivo, seq); descartado (cópia/antigo ou própria origem); sincronização enviada; envelhecido e removido | RF24 (novo); demais = evidência do critério 2 e da Q2 |
| TABELA | recálculo (motivo; tabela inteira só se mudou) | RF24 |
| ENCAMINHA | pacote encaminhado (tipo, origem, destino, próximo salto, TTL novo); também pacotes originados aqui (`enviado`) | RF24 |
| ICMP | **toda** mensagem ICMP gerada: 8 (ping), 0 (resposta de eco), 11, 3 — tipo, destino, id | RF24 |
| ENTREGA / DESCARTE / ERRO | entregue localmente; descartado (malformado, par desconhecido, sem rota); exceção capturada | apoio |
| HELLO | HELLO enviado / recebido — **só no arquivo**, não no terminal (D34) | prova do "HELLO periódico" (critério 1) |

Sem flags (D29). Para o terminal continuar legível: HELLO vai só para o arquivo (D34); cada recálculo
é 1 linha (`tabela recalculada (motivo): sem mudança` ou `... : MUDOU`) e a tabela inteira só é logada
quando muda. Na demo, `tail -f logs/10.6.1.1.log | grep HELLO` mostra o HELLO a cada 5 s.

---

## 5. Topologias de referência

Custos **todos diferentes** e **sem empates** de caminho mínimo (D36): atende "custos diferentes"
na leitura mais forte e deixa a Q1 com resposta única. Tabelas conferidas por cálculo.

**`local5`** (relatório e testes; 1 máquina, `127.0.0.1`, portas 6001–6005). R2 fica no caminho de
R1 para os demais (útil para a Q3):

```
           R1
        1 /  \ 4
         /    \
       R2 ──2── R3           arestas: R1–R2=1, R1–R3=4, R2–R3=2,
       |         |                    R2–R4=7, R3–R5=3, R4–R5=5
     7 |         | 3
       |         |
       R4 ──5── R5
```
| Roteador | Tabela esperada (destino: próximo salto, custo) | Sem R2 |
|---|---|---|
| R1 | R2: R2,1 · R3: R2,3 · R4: R2,8 · R5: R2,6 | R3: R3,4 · R4: R3,12 · R5: R3,7 |
| R2 | R1: R1,1 · R3: R3,2 · R4: R4,7 · R5: R3,5 | — |
| R3 | R1: R2,3 · R2: R2,2 · R4: R5,8 · R5: R5,3 | R1: R1,4 · R4: R5,8 · R5: R5,3 |
| R4 | R1: R2,8 · R2: R2,7 · R3: R5,8 · R5: R5,5 | R1: R5,12 · R3: R5,8 · R5: R5,5 |
| R5 | R1: R3,6 · R2: R3,5 · R3: R3,3 · R4: R4,5 | R1: R3,7 · R3: R3,3 · R4: R4,5 |

(R = roteador 10.6.R.1; sem empates.) Esperado em R1: R2 via R2 (1); R3 via R2 (3); R5 via R2 (6); R4 via R2 (8, enlace R2–R4).
Caminhos alternativos: R1→R3 direto (4) contra via R2 (3); R1→R4 via R2–R3–R5 (11).
Sem R2: R3 via R3 (4); R5 via R3 (7); R4 via R3 (12). (Frederico confirma à mão na Q1.)

**`grupo`** (apresentação; somos trio desde 2026-11-20 → **3 VMs da VDI**, D41/D42). Triângulo:

```
        R1 (William 10.6.1.1)
          1 /          \ 5
           /            \
   R2 (Frederico 10.6.2.1) ──2── R3 (Gustavo 10.6.3.1)
```

| Roteador | Tabela esperada (rede → próximo salto, custo) | Sem R2 | Sem o enlace R1–R2 |
|---|---|---|---|
| R1 | 10.6.2.0/24 → 10.6.2.1, 1 · 10.6.3.0/24 → 10.6.2.1, 3 | 10.6.3.0/24 → 10.6.3.1, 5 | 10.6.3.0/24 → 10.6.3.1, 5 · 10.6.2.0/24 → 10.6.3.1, 7 |
| R2 | 10.6.1.0/24 → 10.6.1.1, 1 · 10.6.3.0/24 → 10.6.3.1, 2 | — | 10.6.3.0/24 → 10.6.3.1, 2 · 10.6.1.0/24 → 10.6.3.1, 7 |
| R3 | 10.6.2.0/24 → 10.6.2.1, 2 · 10.6.1.0/24 → 10.6.2.1, 3 | 10.6.1.0/24 → 10.6.1.1, 5 | 10.6.2.0/24 → 10.6.2.1, 2 · 10.6.1.0/24 → 10.6.1.1, 5 |

Em R1, `ping 10.6.3.1` com TTL 1 e 2 mostra R2 (tempo excedido) e o eco de R3 — caminho R1→R2→R3
(3) em vez do enlace direto (5). Derrubando R2 (ou o enlace R1–R2), R1→R3 passa a usar o enlace
direto — é o caminho alternativo exigido. (IPs reais das VMs preenchidos no dia.)

---

## 6. Fases, ordem e critérios de conclusão

| Fase | Entregas | Concluída quando |
|---|---|---|
| **F0** Fundação (William) | Estrutura de pastas, stubs com as assinaturas da §4, `.gitignore`, `README` inicial, `configs/local5`, esqueleto de testes; teste de fumaça da VDI (`DECISIONS.md`, D24) | Todos os módulos importam; `python3 router.py` sem argumentos mostra o uso; `python3 -m unittest discover tests` passa (`tests/test_interfaces.py`: interfaces, constantes do enunciado, simetria e custos das configs); grupo validou as interfaces; teste de fumaça da VDI passou (ou plano B acionado). *Ajustado na execução: "iniciar com uma config real" dependia do `config.py` (Leonardo, F1) e passou para a F1.* |
| **F1** Base (paralelo) | William (antes Leonardo): `packets.py`, `config.py` · Frederico: `dijkstra.py` · William (P2): `log.py` e `cli.run` mínimo (só `sair`; o resto na F2) · William (P1): Router base + vizinhança | Testes unitários de packets/config/dijkstra passando; `python3 router.py configs/local5/r1.conf` inicia e encerra com `sair`; 2 roteadores locais ficam ativos um para o outro e detectam inatividade em ~20 s (log) |
| **F2** Protocolo (paralelo) | William (P1): LSP/LSDB/inundação/sync/aging · Frederico (antes Leonardo): `forwarding.py` + ping · William (P2): `cli.py` | Testes unitários de LSDB e forwarding passando; 5 roteadores locais com LSDB idêntica e tabelas = esperado da §5 |
| **F3** Integração (P2 coordena) | `tests/integration_local.py`; correções | Integração passa 3 vezes seguidas; todos os RF conferidos localmente; `PROGRESS.md` atualizado |
| **F4** Rede real | Rede do grupo nas 3 VMs da VDI; interoperabilidade com outro grupo da VDI; capturas `.pcapng` (podem ser feitas em uma máquina, com `local5`) | Rede do grupo de 3 VMs funcionando; 1 sessão de interop registrada em log |
| **F5** Entrega | Relatório PDF, README final, `.zip`; ensaio da apresentação; auditoria final | `.zip` descompactado em pasta limpa executa; auditoria com todos os critérios "Atendido" |

Dependências: `packets.py` → (router, forwarding); `dijkstra.py` → recálculo; Router base →
forwarding/CLI. Até a dependência ficar pronta, usar o stub da F0.

---

## 7. Estratégia de testes

- **Unitários** (`python3 -m unittest discover tests`): cada dono escreve os testes do seu módulo
  junto com o código (tabelas das §4.x). O Router é testado sem rede: socket falso que guarda o que
  foi enviado e relógio falso injetado no construtor.
- **Integração local** (`python3 tests/integration_local.py`, ~1 min, 41 verificações; o que depende de
  módulo ainda não implementado aparece como PULADO): sobe os 5 roteadores de `local5`
  como subprocessos, envia comandos pelo stdin, lê a saída e verifica: vizinhos ativos; LSDB com 5
  origens em todos; `tabela` de R1 = §5; `ping` R1→R4 TTL 1..N; `ping 10.99.99.1` (inalcançável, nada
  enviado); `msg`; mata R2 → em ≤ ~25 s a tabela de R1 muda para a rota alternativa; reinicia R2 →
  seq maior aceito; injeção de datagrama malformado e de par desconhecido (roteador continua vivo).
- **Exemplos literais**: todo pacote de exemplo do enunciado vira caso de teste (interop).
- **Manual**: rede real + Wireshark (filtro `udp.port >= 6000 && udp.port <= 6010`; em uma máquina,
  interface loopback); teste com outro grupo.

---

## 8. Fluxo de trabalho no Git

- `main` protegido por convenção: só entra via PR revisado (William + 1 integrante).
- Branches `p1-...`, `p3-...`, `p4-...`; PRs pequenos; testes passando antes do PR.
- Commits e comentários em português. Cada PR atualiza `docs/PROGRESS.md`.
- Revisão cruzada também serve de estudo: quem revisa deve conseguir explicar o código revisado.

---

## 9. Preparação da apresentação (preliminar)

| Parte | Quem conduz | Conceitos que explica |
|---|---|---|
| Abertura, visão geral e condução do roteiro da demo e da interop | **William** | Como os roteadores se comunicam (UDP, formatos), visão do todo |
| Arquitetura, threads, socket único, pacotes, LSP/inundação/sync/aging | William | Descoberta de enlaces, compartilhamento de estado, construção da topologia |
| Dijkstra, tabela, encaminhamento, TTL, ICMP, ping | Frederico | Cálculo de caminhos, atualização de tabelas, encaminhamento de pacotes |
| Vizinhança (HELLO, detecção de falha) ao mostrar a reconvergência; operação de R3 | Gustavo | Deve saber explicar qualquer módulo se perguntado |

Cada um opera seu próprio roteador (R1 William, R2 Frederico, R3 Gustavo).
Todos estudam todos os módulos (regra da IA): sessão de "perguntas do professor" simulada na F5.
O roteiro detalhado (`docs/APRESENTACAO.md`) é escrito pelo William na F5 (antes: Leonardo).

---

## 10. Checklists operacionais (não são código, mas valem nota)

**Regras do enunciado que exigem ação do grupo**
- [x] Informar no Moodle os integrantes (trio: William, Frederico, Gustavo) e avisar o professor
      da mudança (2026-11-21).
- [ ] Informar no Moodle a data de apresentação (e o ambiente, se o Moodle pedir).
- [ ] Prazo de entrega: **antes do início da primeira aula de apresentação** (de qualquer grupo, não
      só da nossa). Atraso não é aceito.
- [ ] Testes de interoperabilidade com outros grupos: trocar só pacotes, **nunca código** (cópia ⇒
      zero para todos os envolvidos).
- [ ] `.zip`: código-fonte sem `__pycache__`/binários, `README`, relatório PDF, capturas `.pcapng`;
      descompactar em pasta limpa e executar antes de enviar.

**Antes da apresentação (rede montada no início do horário)**
- [ ] Cada VM: código atualizado, `python3 --version` ≥ 3.8, IP anotado, config com os IPs do dia.
- [ ] Subir os 3 roteadores, esperar ~10 s, conferir `vizinhos`/`lsdb`/`tabela` com a §5.

**Comportamentos do protocolo que o professor pode perguntar (são do enunciado, não defeitos)**
- Ao derrubar um roteador, a rota só muda depois de **até ~20 s** (detecção por ausência de HELLO).
- O LSP do roteador derrubado continua na `lsdb` por até **90 s** (envelhecimento), mas ele some da
  `tabela` assim que os vizinhos geram LSPs sem ele (ninguém mais tem aresta até ele).
- Logo depois de uma queda, por alguns segundos um roteador pode ainda ter rota para o roteador
  caído, passando por um vizinho que ainda não detectou a queda (o LSP antigo dele ainda lista o
  caído). A rota some quando os vizinhos do caído inundam LSPs novos (até ~20 s). Visto em
  `tests/test_router.py::test_queda_de_r2_usa_caminho_alternativo`; bom exemplo para a Q3/Q6.
- Reiniciar o roteador derrubado **depois** de os vizinhos o marcarem inativo (~20 s): aí eles o
  veem ficar ativo de novo e fazem a sincronização. Se reiniciar antes, os vizinhos não percebem a
  queda, não sincronizam, e ele só completa a LSDB nas renovações (até 30 s).
- Derrubar só um **enlace**: comentar a linha `vizinho` em um dos lados e reiniciar esse roteador; o
  outro lado detecta a queda em ~20 s. Esperar ~30 s antes de conferir as tabelas (motivo acima).
