# Guia de estudo do código

> **Por que este guia existe:** o enunciado diz que *todos os integrantes devem ser capazes de
> explicar qualquer parte do código*, e que código que o integrante questionado não consiga explicar
> leva o trabalho a **nota zero**. Cada um precisa conhecer também as partes que não escreveu.
>
> Cada dono escreve a parte dele. Parte 1 (esta): `router.py`, `log.py` e `cli.py`, escritos pelo
> William. Parte 3 (`dijkstra.py`, Frederico) já escrita. Partes pendentes: `packets.py`,
> `config.py` e `forwarding.py` (Leonardo).
>
> Como estudar: leia uma seção, abra o arquivo ao lado e encontre a função citada. No fim há
> perguntas prováveis do professor e uma lista "consigo explicar...?" para conferir.

---

## Parte 1 — `router.py`, `log.py`, `cli.py` (William)

### 1. O roteador em 1 minuto

O programa é **um roteador** da rede virtual. Ele conversa com os vizinhos por UDP, e todos os
pacotes são texto ASCII com campos separados por `:`. O ciclo completo:

1. **Descobre os vizinhos** mandando e recebendo `HELLO` (seção 4).
2. **Monta o próprio LSP**, a lista "meus vizinhos ativos e o custo até cada um", e manda aos vizinhos (seção 5).
3. **Inunda os LSPs**: o LSP de outro roteador que chega é repassado aos demais vizinhos. Assim
   todos acabam com a **mesma LSDB**, isto é, a topologia inteira (seção 5).
4. **Calcula a tabela** com Dijkstra sobre a LSDB (seção 6).
5. **Encaminha** DADOS e ICMP usando a tabela (é o `forwarding.py`, do Leonardo).
6. **Mostra tudo no terminal e no log** (seções 8 e 9).

Isso é **estado de enlace**: cada roteador conhece o mapa inteiro e calcula sozinho os caminhos.
No **vetor de distância** é diferente: cada roteador só conta aos vizinhos "chego em X com custo Y"
e confia na conta deles; ninguém tem o mapa.

### 2. Quem chama quem

```
router.py  main()
  ├─ config.load_config()        lê o arquivo de configuração           (Leonardo)
  ├─ Logger(...)                 log.py: abre logs/<endereço>.log       (William)
  ├─ Router(...)                 o estado do roteador                   (William)
  ├─ Forwarder(router)           encaminhamento e ping                  (Leonardo)
  ├─ router.start()              socket + 1º HELLO + 2 threads
  └─ cli.run(router, forwarder)  lê os comandos do usuário              (William)

Router usa: packets.parse/encode (ler e montar pacotes, Leonardo)
            dijkstra.dijkstra    (calcular caminhos, Frederico)
```

### 3. As três threads e o lock

Uma *thread* é uma "linha de execução" dentro do mesmo programa. O roteador tem 3, rodando ao mesmo tempo:

| Thread | Função | O que faz |
|---|---|---|
| principal | `cli.run` | espera o usuário digitar e executa o comando |
| recepção | `Router.receive_loop` | fica parada em `recvfrom()` até chegar um datagrama; então chama `handle_datagram` |
| temporizador | `Router.timer_loop` | a cada 0,5 s chama `tick()`, que cuida de tudo que depende de tempo |

**Por que um lock (`self.lock`)?** As três mexem no mesmo estado: vizinhos, LSDB e tabela. Sem
lock, a recepção poderia estar alterando a LSDB no exato momento em que o temporizador apaga um LSP
velho, e o estado ficaria inconsistente. Com o lock, quem entra em `with self.lock:` executa até o
fim antes de outra thread entrar. Usamos **um único lock** para tudo (decisão D02), porque é o mais
simples de acertar e de explicar.

**Por que `RLock` e não `Lock`?** O "R" é de *reentrante*: a mesma thread pode entrar de novo
sem travar a si mesma. Isso acontece, por exemplo, quando `handle_datagram`, já dentro do lock,
chama `forwarder.handle`, que chama `router.route_for`, que também usa o lock.

**Por que as threads são `daemon=True`?** Assim, quando o usuário digita `sair` e a thread
principal termina, o programa encerra sem precisar parar as outras duas.

### 4. Vizinhança (HELLO) — critério 1

Estado de cada vizinho (classe `Neighbor`): `cost` vem do arquivo de configuração; `virtual` é o
endereço virtual aprendido pelo HELLO; `active` diz se está ativo; `last_hello` guarda quando chegou
o último HELLO. Os vizinhos ficam num dicionário **indexado pelo par (IP real, porta)**, porque é
assim que o `recvfrom` diz de onde veio um pacote.

| Regra do enunciado | Onde está |
|---|---|
| HELLO a cada 5 s para **todos os configurados** | `tick()`: se `last_hello_sent` é `None` (partida) ou passaram 5 s, manda `HELLO:<meu endereço>` a cada par de `self.neighbors` |
| Vizinho fica **ativo** no 1º HELLO; associa endereço virtual ↔ (IP, porta) | `handle_hello()`: se não estava ativo, `active = True` e `virtual = pkt.addr` |
| **20 s** sem HELLO → inativo | `tick()`: `agora - last_hello >= 20` → `active = False` |
| Toda mudança na lista de ativos gera **imediatamente** um LSP | `handle_hello()` e `tick()` chamam `generate_own_lsp()` logo depois de mudar `active` |

**Por que HELLO para todos os configurados, e não só para os ativos?** Se mandássemos só aos
ativos, ninguém nunca ficaria ativo: um vizinho só fica ativo depois de receber o nosso HELLO.

**Por que `time.monotonic()` para medir os 20 s?** É um relógio que só anda para frente. O relógio
de parede (`time.time()`) pode pular se alguém acertar a hora da máquina, e um pulo podia derrubar
vizinhos à toa. O relógio é passado no construtor (`clock=`) para os testes usarem um relógio falso.

### 5. LSPs, inundação, sincronização e envelhecimento — critério 2

Estado: `self.lsdb` é um dicionário `{origem: LsdbEntry}`. Cada `LsdbEntry` tem `seq`, `neighbors`
(`{vizinho: custo}`) e `received_at` (quando foi aceito; `None` no LSP próprio).

**5.1 Geração do LSP próprio (`generate_own_lsp`)**
- Quando: vizinho ficou ativo ou inativo, e a renovação a cada 30 s (`tick()`). **Não** há LSP na
  partida, porque a partida não está entre os gatilhos do enunciado (D30).
- Número de sequência: o 1º é `int(time.time())`, o Unix time em segundos; depois, `seq + 1`.
- Conteúdo: só os vizinhos **ativos**, com o custo da configuração. Sem vizinhos ativos, a lista
  fica vazia: `LSP:10.6.1.1:1795111000:`.
- Grava na própria LSDB, envia a todos os ativos e recalcula a tabela.

**Por que o seq começa no Unix time?** Se o roteador reiniciar, o novo seq (a hora atual) será
maior que todos os que ele usou antes: ele soma 1 a cada LSP, e a hora soma 1 a cada segundo. Os
outros aceitam o LSP novo na hora (regra 2).

**5.2 Recebimento (`handle_lsp`)**: as 3 regras do enunciado, na ordem:
1. A origem sou eu? → descarta. É uma cópia do meu próprio LSP que voltou pela inundação.
2. A LSDB já tem LSP dessa origem com seq **maior ou igual**? → descarta (cópia ou LSP antigo).
3. Senão → guarda, **repassa a todos os vizinhos ativos menos quem mandou**, e recalcula a tabela.

Cada caso gera uma linha de log ("descartado (propria origem)", "descartado (copia/antigo)",
"LSP novo"). Somando as linhas dos 5 roteadores, dá para contar quantos LSPs circularam (Q2 do
relatório).

**Por que não repassar para quem mandou?** Ele já tem esse LSP. Mandar de volta só gasta banda (e
ele descartaria pela regra 2).

**Por que a inundação termina?** Cada roteador repassa um LSP **uma única vez**: na segunda vez em
que a mesma cópia chega, a regra 2 descarta. Então, na inundação, cada LSP passa por cada enlace no
máximo uma vez em cada sentido, e para. (As cópias da sincronização são enviadas uma vez só, ao
vizinho novo, e também param na regra 2.)

**Por que repassar `packets.encode(pkt)` em vez do datagrama original?** Garante que só sai do
nosso roteador o formato exato, mesmo que o pacote tenha chegado com um `\n` no fim (D35). O seq
continua o mesmo, como o enunciado manda.

**5.3 Sincronização (`sync_neighbor`)**: quando um vizinho fica ativo, além do LSP próprio novo,
ele recebe uma cópia de **todos** os LSPs da LSDB, inclusive o próprio (D31). Sem isso, um roteador
recém-chegado só conheceria os outros na próxima renovação (até 30 s).

**5.4 Envelhecimento (`tick()`)**: o LSP de outro roteador que fica 90 s sem ser renovado (sem
chegar um seq maior) é apagado, e a tabela é recalculada. O LSP próprio tem `received_at = None` e
nunca envelhece. É o que tira da LSDB um roteador que saiu de vez da rede.

### 6. Tabela de roteamento — critério 3

**`recompute(motivo)`** roda sempre que a LSDB muda:
1. monta o grafo `{origem: {vizinho: custo}}` a partir da LSDB;
2. chama `dijkstra.dijkstra(grafo, meu_endereço)` (do Frederico), que devolve
   `{roteador destino: (próximo salto, custo)}`;
3. troca cada roteador destino pela rede dele (`10.6.3.1` → `10.6.3.0/24`);
4. registra no log uma linha "sem mudanca", ou "MUDOU" seguido da tabela nova.

**`route_for(destino)`** é o que o encaminhamento usa: acha a rede do destino na tabela, pega o
próximo salto (um endereço virtual) e devolve o par (IP real, porta) do vizinho ativo que tem esse
endereço. É assim que um endereço virtual vira um envio UDP de verdade.

### 7. Robustez — "sem derrubar o roteador"

- `handle_datagram`: pacote de um par fora da configuração → descarta e loga; pacote malformado
  (`packets.MalformedPacket`) → descarta e loga.
- `receive_loop` e `timer_loop` envolvem o trabalho em `try/except Exception` (D33): qualquer erro
  inesperado vira uma linha `[ERRO]` no log e a thread continua viva.
- `send()` captura `OSError` (erro de rede ao enviar).
- `cli.run` também captura erro de um comando (D38).

### 8. `log.py`

- Cada linha: `2026-11-19 16:01:02.123 [CATEGORIA] texto`. Os milissegundos servem para medir a
  convergência (Q3).
- `flush()` logo depois de escrever: a linha vai para o disco **na hora** ("salvar em logs em tempo real").
- O arquivo é aberto com `"a"` (acrescentar): um reinício não apaga o histórico (D37).
- Tem um lock próprio, para linhas de threads diferentes não se misturarem.
- `terminal=False` só no HELLO: ele vai para o arquivo, mas não enche a tela (D34).
- Tudo sem acento (D39): um teste real mostrou que acento pode derrubar o programa num terminal sem suporte.

### 9. `cli.py`

- `run()` repete: lê uma linha (`input`), chama `executar()`, mostra o texto. Termina com `sair`,
  Ctrl+C ou fim da entrada.
- `executar()` devolve `(texto, continuar)`. Separar assim deixa testar cada comando sem teclado.
- `tabela`, `lsdb` e `vizinhos` só formatam o que o Router devolve (`get_table`, `get_lsdb`,
  `get_active_neighbors`), em ordem numérica de endereço (`chave_endereco`).
- `msg`: o texto é o resto da linha (`split(None, 2)`); é recusado se tiver `:` ou acento.
- `ping`: o TTL padrão é 16 e precisa ser um inteiro ≥ 1 (`so_digitos`). Quem envia e espera a
  resposta é o `forwarding.py`.

### 10. Exemplo completo: a rede do grupo

Topologia: R1–R2 = 1, R2–R4 = 2, R4–R3 = 3, R3–R1 = 7 (plano §5).

**Subida (cerca de 5 s até convergir):**
1. Cada roteador liga e manda HELLO aos vizinhos configurados. Quem ainda não ligou não recebe; tudo bem.
2. R1 recebe o HELLO de R2 → R2 fica **ATIVO** → R1 gera o LSP `LSP:10.6.1.1:S:10.6.2.1=1` e manda
   a R2 → em seguida manda a R2 cópia de toda a sua LSDB (sincronização).
3. R2 faz o mesmo com R1. O LSP de R2 chega a R1 → regra 3: é novo → R1 guarda, repassa a R3 (se
   já estiver ativo) e recalcula a tabela.
4. Depois de alguns HELLOs (≤ 5 s), todos têm os 4 LSPs. A tabela de R1 fica: R2 via R2 (1),
   R4 via R2 (3), R3 via R2 (6, pelo caminho R1→R2→R4→R3, mais barato que o enlace direto de 7).

**Queda de R2 (o professor encerra o processo):**
1. R2 para de mandar HELLO. O último saiu, no máximo, 5 s antes da queda.
2. Entre 15 e 20 s depois da queda, R1 e R4 marcam R2 **INATIVO**, cada um no seu tempo, e geram LSPs sem R2.
3. **Estado transitório:** se R1 detectar antes de R4, por alguns instantes o LSP antigo de R4
   ainda diz "R4–R2 existe", e R1 calcula uma rota até R2 por R3 e R4 (custo 12). Quando o LSP novo
   de R4 chega, essa rota some. É normal, e é um bom exemplo para a Q3 e a Q6.
4. Tabela final de R1: R3 via R3 (7), R4 via R3 (10). O LSP antigo de R2 continua na `lsdb` até
   envelhecer (90 s), mas não aparece na tabela, porque ninguém mais tem aresta até R2.
5. **Reinício de R2** (depois de os vizinhos o marcarem inativo): ele volta com seq = hora atual,
   maior que o antigo; os vizinhos o veem ficar ativo, fazem a sincronização, e as tabelas voltam.

### 11. Perguntas prováveis do professor (com resposta)

1. **Por que um socket só?** O enunciado exige enviar e receber pelo mesmo socket. Assim, a porta de
   origem dos nossos pacotes é a porta do roteador, e o vizinho nos reconhece pelo par (IP, porta)
   da configuração.
2. **Como o roteador sabe que um vizinho caiu?** Pela ausência de HELLO: 20 s sem nenhum → inativo.
   UDP não tem conexão, então não há outro jeito.
3. **Quanto tempo leva para a rota mudar depois de uma queda?** De 15 a 20 s para detectar (depende
   de quando foi o último HELLO), mais alguns milissegundos de inundação e Dijkstra. Quase todo o
   tempo é detecção (Q3).
4. **Para que serve o número de sequência?** Para saber qual LSP de uma origem é o mais novo, e
   descartar cópias e LSPs atrasados. Sem ele, a inundação não teria como parar.
5. **E se o roteador reiniciado voltasse a numerar a partir de 0?** Os outros têm um LSP dele com seq
   enorme (o Unix time) e descartariam os novos pela regra 2, como se fossem antigos. A informação
   errada sobre ele ficaria até o LSP antigo envelhecer (90 s). Por isso o seq começa na hora atual (Q4).
6. **E se um LSP se perder (UDP não confirma)?** Alguns roteadores ficam com a LSDB desatualizada
   até a próxima renovação (≤ 30 s), que traz um seq maior e corrige. O envelhecimento (90 s) apaga
   o que não é mais renovado, e a sincronização cobre roteadores que acabaram de chegar (Q5).
7. **Se todos calculam sobre a mesma topologia, por que TTL?** Durante a convergência, as LSDBs
   **não** são iguais: um roteador já soube da queda e outro ainda não. Exemplo: R1 já recalculou e
   manda um pacote para X por R3; R3 ainda não soube e devolve para R1. O pacote ficaria indo e
   voltando para sempre; o TTL chega a 0 e o pacote morre, com ICMP 11 (Q6).
8. **Por que o roteador derrubado continua na `lsdb`?** O enunciado só tira LSPs da LSDB por
   substituição (seq maior) ou envelhecimento (90 s). Ele já não aparece na **tabela**, porque
   nenhum LSP atual tem aresta até ele.
9. **Por que não repassar o LSP para quem o mandou?** Ele já tem esse LSP; seria tráfego inútil.
10. **Por que o LSP próprio não sai assim que o roteador liga?** O enunciado lista só dois gatilhos:
    mudança de vizinho e renovação de 30 s. Ao ligar não há vizinho ativo; o 1º LSP sai quando o
    primeiro vizinho fica ativo.
11. **O que acontece com um pacote de um IP/porta que não está na configuração?** É descartado
    antes de ser lido (`handle_datagram`), com uma linha no log.
12. **E com um pacote malformado?** `packets.parse` levanta `MalformedPacket`; o roteador descarta,
    loga e continua.
13. **Por que um lock só?** As 3 threads mexem no mesmo estado; um lock único garante que uma operação
    termina antes de outra começar, e é fácil de explicar.
14. **O que é a LSDB?** A base de estados de enlace: o último LSP de cada roteador da rede. Vira um
    grafo, e o Dijkstra roda sobre ele.
15. **Diferença entre estado de enlace e vetor de distância?** No estado de enlace, cada roteador
    inunda a lista dos seus vizinhos, todos montam o mapa inteiro e calculam com Dijkstra. No vetor de
    distância, cada um manda aos vizinhos só "distância até cada destino", e ninguém tem o mapa.
16. **Para que serve o tick de 0,5 s?** É a frequência com que o temporizador confere os prazos
    (5, 20, 30, 90 s). Com 0,5 s, a inatividade é detectada entre 20 e 20,5 s.

### 12. Para conferir na prática

```bash
python3 -m unittest discover tests     # testes unitários
python3 tests/integration_local.py     # 5 roteadores reais, ~1 minuto
```
Depois que o `config.py` existir, abra 5 terminais com `python3 router.py configs/local5/rN.conf`
(N de 1 a 5) e experimente `vizinhos`, `lsdb` e `tabela`. Encerre um deles com `sair` e acompanhe o
log dos outros com `tail -f logs/10.6.1.1.log`.

### 13. Consigo explicar...?

- [ ] o que cada uma das 3 threads faz, e por que existe o lock;
- [ ] como um vizinho fica ativo e como fica inativo, e em quanto tempo;
- [ ] quando o roteador gera um LSP e de onde vem o número de sequência;
- [ ] as 3 regras de recebimento de LSP, e por que a inundação termina;
- [ ] para que servem a sincronização e o envelhecimento;
- [ ] como a LSDB vira tabela, e como `route_for` transforma endereço virtual em (IP, porta);
- [ ] o que acontece, passo a passo, quando um roteador cai e quando ele volta;
- [ ] as perguntas da seção 11 sem olhar a resposta.

---

## Parte 2 — `packets.py`, `config.py`, `forwarding.py` (Leonardo)

*A escrever pelo Leonardo quando os módulos estiverem prontos.*

## Parte 3 — `dijkstra.py` (Frederico)

### 1. O que o módulo faz

Uma única função, `dijkstra(graph, source)`. Ela recebe a LSDB já convertida em grafo e devolve,
para cada roteador alcançável, **por qual vizinho sair e quanto custa chegar lá**:

- entrada: `graph = {nó: {vizinho: custo}}` e `source` (o próprio endereço virtual);
- saída: `{destino: (proximo_salto, custo)}`, sem incluir o `source`.

Quem chama é o `Router.recompute` (`router.py`), sempre que a LSDB muda. O Router converte cada
destino na rede dele (`10.6.3.1` → `10.6.3.0/24`) e guarda o resultado em `self.table`.

### 2. Como o algoritmo funciona

Variáveis (todas locais à função):

| Variável | Para que serve |
|---|---|
| `custo` | menor custo **conhecido** até cada nó (provisório até o nó ser finalizado) |
| `primeiro_salto` | vizinho do `source` pelo qual começa o melhor caminho até cada nó (vira o "próximo salto" da tabela) |
| `finalizados` | nós cujo custo já é definitivo |
| `fila` | fila de prioridade (`heapq`) com tuplas `(custo, nó)` |

Passo a passo:
1. Se o `source` não está no grafo (o roteador recebeu LSPs antes de gerar o próprio), devolve `{}`.
2. Começa com `custo[source] = 0` e a fila com `(0, source)`.
3. Repete: tira da fila o nó de **menor custo** (`heappop`). Se já foi finalizado, ignora (é uma
   entrada antiga). Senão, finaliza.
4. **Relaxamento:** para cada aresta que **sai** desse nó, calcula `novo_custo = custo_no + peso`.
   Se for menor que o custo conhecido do vizinho, atualiza `custo`, atualiza `primeiro_salto` e
   empilha `(novo_custo, vizinho)`.
5. Quando a fila acaba, devolve `(primeiro_salto, custo)` de todos os nós alcançados.

**Como o próximo salto é obtido sem reconstruir o caminho:** se a aresta sai do próprio `source`,
o vizinho é o primeiro salto dele mesmo; senão, ele herda o primeiro salto do nó de onde veio
(`primeiro_salto[no]`). Assim a informação já está pronta quando o algoritmo termina.

### 3. Decisões que aparecem no código

- **Grafo dirigido (D07):** só se usam as arestas O → vizinho do LSP de O, sem checar se o vizinho
  também lista O. É o que o enunciado descreve.
- **Nó que só aparece como vizinho:** também é destino. Por isso o código usa
  `graph.get(no, {})`: esse nó não tem LSP próprio na LSDB, e o `get` evita erro.
- **Empate:** qualquer caminho de custo mínimo serve (enunciado). Fica o primeiro encontrado: só
  se atualiza com `<` estrito.
- **Custos positivos:** o `packets.py` rejeita custo 0 ou negativo. O Dijkstra só é correto com
  custos positivos: é isso que garante que o nó retirado da fila já tem custo definitivo.
- **`heapq` não diminui prioridade:** em vez disso, empilha-se uma nova entrada e as antigas são
  ignoradas ao sair da fila (`if no in finalizados: continue`).
- **Proibido** usar networkx, scipy etc.; `heapq` é da biblioteca padrão e é permitido.

### 4. Exemplo: R1 na `local5` (iterações, como na aula)

Arestas: R1–R2=1, R1–R3=4, R2–R3=2, R2–R4=7, R3–R5=3, R4–R5=5.

| Passo | N' (finalizados) | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| 0 | R1 | 1, R2 | 4, R3 | ∞ | ∞ |
| 1 | R1, R2 | | 3, R2 | 8, R2 | ∞ |
| 2 | R1, R2, R3 | | | 8, R2 | 6, R2 |
| 3 | R1, R2, R3, R5 | | | 8, R2 (via R5 seria 11) | |
| 4 | R1, R2, R3, R5, R4 | | | | |

Cada célula é `custo, próximo salto`. Resultado: R2 (R2, 1), R3 (R2, 3), R4 (R2, 8), R5 (R2, 6),
igual à tabela esperada de R1 no plano §5. Este é o ponto de partida da Q1 do relatório.

### 5. Perguntas prováveis do professor (com resposta)

1. **Por que usar `heapq`?** Ele entrega o nó pendente de menor custo em O(log n), sem varrer todos.
2. **Qual a complexidade?** O((V + E) log V), com V roteadores e E arestas.
3. **Por que o nó retirado da fila já tem custo definitivo?** Porque os custos são positivos:
   qualquer outro caminho passaria por nós de custo maior ou igual, e só poderia ficar mais caro.
4. **Como você descobre o próximo salto?** Propagando o primeiro salto durante o relaxamento: o
   vizinho direto do `source` é o próprio primeiro salto; os demais herdam o do nó anterior.
5. **Por que ignorar entradas antigas da fila?** O `heapq` não permite diminuir a prioridade; quando
   o custo de um nó melhora, entra uma entrada nova, e a velha, ao sair, já encontra o nó finalizado.
6. **O que acontece se o `source` não está no grafo?** Devolve `{}`: não há por onde começar. Pode
   ocorrer se chegarem LSPs de outros antes de o roteador gerar o próprio.
7. **Por que o grafo é dirigido?** Cada LSP só informa as arestas que saem da própria origem (D07).
8. **O que acontece com um nó que só aparece como vizinho?** Vira destino normalmente; o `get(no, {})`
   o trata como um nó sem arestas de saída.
9. **E se houver empate?** Qualquer caminho de custo mínimo é aceito; o código fica com o primeiro
   encontrado.
10. **Quando o Dijkstra roda?** A cada mudança na LSDB: LSP novo, LSP próprio novo ou
    envelhecimento (`Router.recompute`).
11. **Por que a rota para um roteador caído pode existir por alguns segundos?** O Dijkstra calcula
    sobre o que a LSDB diz. Enquanto um LSP antigo ainda lista o caído, a aresta existe e a rota
    também; some quando os LSPs novos chegam.
12. **Onde você garante que o resultado não inclui o próprio roteador?** `primeiro_salto` nunca recebe
    o `source`: ele já está finalizado quando suas arestas são relaxadas, então nenhuma aresta o
    atualiza.

### 6. Para conferir na prática

```bash
python3 -m unittest tests.test_dijkstra -v
```

### 7. Consigo explicar...?

- [ ] o papel de `custo`, `primeiro_salto`, `finalizados` e `fila`;
- [ ] o laço principal e o relaxamento, linha por linha;
- [ ] como o próximo salto é obtido sem reconstruir o caminho;
- [ ] por que as entradas antigas da fila são ignoradas;
- [ ] por que o grafo é dirigido e como tratar um nó que só aparece como vizinho;
- [ ] o exemplo da seção 4 sem olhar a tabela;
- [ ] as perguntas da seção 5 sem olhar a resposta.