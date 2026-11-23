# PROJECT_CONTEXT — Roteador de estado de enlace sobre UDP

> **Leia este arquivo primeiro ao retomar o trabalho.** Ele resume tudo o que é preciso para
> continuar sem reinterpretar o enunciado.
>
> - Enunciado completo (fonte de verdade): [`ENUNCIADO.md`](ENUNCIADO.md)
> - Plano detalhado, interfaces e testes: [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)
> - Decisões e interpretações (com status): [`DECISIONS.md`](DECISIONS.md)
> - Andamento: [`PROGRESS.md`](PROGRESS.md)
> - Guia de estudo do código (todos precisam saber explicar tudo): [`GUIA_ESTUDO.md`](GUIA_ESTUDO.md)
>
> Última atualização: 2026-11-20 (Leonardo saiu do grupo: grupo virou **trio**, tarefas redivididas na §7).
>
> **Dados fixos:** Grupo **G = 6** · ambiente **VDI** · Python 3 (stdlib) · integrantes: William
> (faz também a parte do Gustavo), Frederico e Gustavo (apresenta e opera R3). **Trio** desde
> 2026-11-20: Leonardo saiu do grupo; a apresentação usa 3 roteadores (enunciado: "3 nos trios").
> **Regra de desempate:** quando o enunciado não define algo, escolher o que cumpre o texto e é mais
> simples de explicar (ver `DECISIONS.md`).

---

## 1. Resumo e objetivo

Implementar um **roteador de estado de enlace** (inspirado no OSPF, mas **não** o OSPF completo)
como uma aplicação sobre **UDP**. Cada integrante roda uma instância em sua máquina; juntas formam
uma rede virtual (endereços `10.G.R.1`, redes `10.G.R.0/24`) sobre a rede local real.

Cada roteador: descobre vizinhos com **HELLO** → gera e **inunda LSPs** → monta a **LSDB** →
calcula a tabela com **Dijkstra** (implementado pelo grupo) → **encaminha** DADOS/ICMP com **TTL** →
implementa `ping`, tempo excedido (11) e destino inalcançável (3).

O formato dos pacotes deve ser seguido **à risca**: na apresentação a nossa rede será ligada à de
outro grupo (critério 7, 10%).

---

## 2. Requisitos extraídos do enunciado

IDs usados no plano, nos testes e na auditoria final. Texto exato em `ENUNCIADO.md`.

### Configuração e socket
| ID | Requisito |
|---|---|
| RF01 | Arquivo de configuração lido ao iniciar, com: endereço virtual `10.G.R.1`, porta UDP local (padrão **6000**), lista de vizinhos com **IP real, porta UDP, custo inteiro positivo**. Formato livre, fácil de editar. |
| RF02 | **Um único socket UDP** ligado à porta configurada, usado para enviar **e** receber. |
| RF03 | Descartar pacotes vindos de um par (IP real, porta) que **não está** na lista de vizinhos configurados. |
| RF04 | Descartar pacotes **malformados** sem derrubar o roteador (tipo desconhecido, nº errado de campos, valores não numéricos, mensagem com `:` ou não ASCII). |

### Vizinhança (critério 1)
| ID | Requisito |
|---|---|
| RF05 | Enviar `HELLO:<end. virtual>` **a cada 5 s** a todos os vizinhos configurados. |
| RF06 | Vizinho fica **ativo** no primeiro HELLO; associar end. virtual do HELLO ao par (IP real, porta) de origem. |
| RF07 | Vizinho sem HELLO por **20 s** fica **inativo**. |
| RF08 | Toda entrada/saída da lista de ativos gera **imediatamente** um novo LSP. |

### LSPs e inundação (critério 2)
| ID | Requisito |
|---|---|
| RF09 | Gerar LSP próprio quando vizinho fica ativo/inativo e **a cada 30 s** (renovação). |
| RF10 | Nº de sequência próprio: primeiro = **Unix time em segundos**; +1 a cada novo LSP. Ao reenviar LSP alheio, o nº **não muda**. |
| RF11 | LSP próprio lista **só vizinhos ativos** com custo configurado; é enviado a todos os ativos e guardado na própria LSDB. Lista vazia: `LSP:<o>:<seq>:`. |
| RF12 | Recebimento: (1) origem = eu → descarta; (2) LSDB tem seq **≥** → descarta; (3) senão substitui, **reenvia a todos os ativos exceto V** e recalcula a tabela. |
| RF13 | Sincronização: quando um vizinho fica ativo, enviar **a ele** todos os LSPs da LSDB (além do novo LSP próprio). |
| RF14 | Envelhecimento: LSP de outro roteador não renovado por **90 s** é removido e a tabela recalculada. |

### Tabela de roteamento (critério 3)
| ID | Requisito |
|---|---|
| RF15 | **Dijkstra implementado pelo grupo** (proibido networkx, scipy.csgraph etc.; `heapq` permitido), a partir de si mesmo, sobre o grafo da LSDB (cada LSP de O = arestas O→vizinho com o custo). |
| RF16 | Entrada por roteador alcançável R: **rede `10.G.R.0/24`**, **próximo salto** (end. virtual do vizinho que inicia o caminho mínimo), **custo** (soma). Empate: qualquer caminho mínimo. |
| RF17 | Recalcular **sempre que a LSDB muda**. |

### Encaminhamento e ICMP (critérios 4 e 5)
| ID | Requisito |
|---|---|
| RF18 | Ao originar DADOS/ICMP: sem rota → avisar "destino inalcançável" ao usuário **sem enviar**; com rota → enviar com TTL inicial (16 ou o do `ping`) ao (IP, porta) do próximo salto. |
| RF19 | Destino na própria `/24`: entregar ao roteador. DADOS → exibir origem, destino, mensagem. ICMP 8 → responder tipo 0, mesmo id, **origem = destino do pedido**. ICMP 0/11/3 → exibir ao usuário. |
| RF20 | Destino em outra rede: decrementar TTL; se chegar a 0 → descartar + **ICMP 11** à origem; sem rota → descartar + **ICMP 3** à origem; senão encaminhar com o novo TTL. |
| RF21 | Erros (11/3) gerados: origem = end. virtual do roteador, **TTL 16**, **id copiado**. **Nunca** gerar erro em resposta a erro. |

### Interface e logs (critério 6)
| ID | Requisito |
|---|---|
| RF22 | Programa único em um terminal; lê comandos e mostra resultados e logs no mesmo terminal. |
| RF23 | Comandos: `tabela`, `lsdb`, `vizinhos`, `msg <destino> <texto>`, `ping <destino> [TTL]` (padrão 16; mostra tipo da resposta, quem enviou, RTT, ou **timeout após 2 s**). |
| RF24 | Logs salvos em tempo real: vizinho ativo/inativo, LSPs novos recebidos, recálculos da tabela, pacotes encaminhados (próximo salto e TTL), ICMP gerados. |

### Não funcionais
| ID | Requisito |
|---|---|
| RNF01 | UDP, texto **ASCII**, campos separados por `:`, formatos exatos (interoperabilidade). |
| RNF02 | Ambiente único para o grupo: **VDI (só Python)** ou **access point (qualquer linguagem)**. |
| RNF03 | API de sockets UDP usada diretamente; sem bibliotecas de grafos/roteamento. |
| RNF04 | Trabalho que não executa não é avaliado. |
| RNF05 | **Todos** devem conseguir explicar **qualquer** parte do código; código não explicável ⇒ **nota zero** (regra sobre IA). |
| RNF06 | Sem cópia entre grupos (nota zero para todos os envolvidos). |

### Entregáveis (prazo: antes do início da 1ª aula de apresentação; atraso não aceito)
| ID | Entregável |
|---|---|
| E01 | `.zip` enviado por um integrante, com: código-fonte (sem binários/build), `README` (execução + formato do arquivo de configuração), relatório **PDF**, capturas **`.pcapng`** usadas no relatório. |

### Relatório (critério 8)
Topologia de teste com **≥ 5 roteadores**, custos diferentes, **≥ 1 caminho alternativo**, com figura.
Pode ser em uma única máquina (portas diferentes). Questões Q1–Q6 com evidências (logs, saídas,
Wireshark): Q1 Dijkstra passo a passo vs. `tabela`; Q2 contagem de LSPs após queda de um vizinho,
cópias descartadas, comparação com vetor de distância; Q3 tempo de convergência (detecção vs.
inundação+recálculo, relação com timers do HELLO); Q4 nº de sequência e reinício a partir de 0;
Q5 perda de LSP e mecanismo de recuperação; Q6 por que TTL e exemplo de laço na convergência.

### Apresentação
- Rede do grupo **montada e funcionando** no início do horário ("4 roteadores nos quartetos, 3 nos
  trios": somos trio → **3 roteadores**, 1 por integrante, custos diferentes, ≥ 1 caminho
  alternativo, todos no mesmo ambiente).
- Roteiro (~10 min): `vizinhos`/`lsdb`/`tabela` em cada roteador; `ping` TTL 1,2,3… até o mais
  distante + `msg`; `ping` para rede inexistente; professor derruba roteador/enlace → reconvergência
  + `ping` TTL crescente com novo caminho → roteador reiniciado; perguntas sobre o código.
- Interoperabilidade (~5 min): enlace com o outro grupo (1 linha a mais na config de cada lado);
  `lsdb`/`tabela` com roteadores do outro grupo; `ping` TTL crescente e `msg` atravessando; reconvergência
  quando o enlace entre grupos cai.
- Todos presentes. Recomenda-se testar com outros grupos antes.

---

## 3. Critérios de avaliação × implementação × comprovação

| # | Critério | Peso | Requisitos | Onde é implementado | Como será comprovado |
|---|---|---|---|---|---|
| 1 | Vizinhança | 5% | RF05–RF08 | `router.py` (timers, HELLO, estado dos vizinhos) | Testes unitários do estado de vizinho; log "vizinho ATIVO/INATIVO"; HELLO a cada 5 s no arquivo de log (D34); demo: `vizinhos` antes/depois de derrubar um roteador (inativo em ~20 s). |
| 2 | LSPs e inundação | 20% | RF09–RF14 | `router.py` (geração, seq, inundação, sync, aging) + `packets.py` | Testes unitários das regras 1–3 e do aging; teste de integração com 5 roteadores; logs "LSP novo", "LSP descartado", "LSP sincronização", "LSP envelhecido"; `lsdb` mostrando seq; captura Wireshark; reinício com seq maior. |
| 3 | Tabela de roteamento | 15% | RF15–RF17 | `dijkstra.py` (puro) + recálculo em `router.py` | Testes unitários com grafos conhecidos (empate, inalcançável); `tabela` conferida com a topologia; Q1 do relatório (passo a passo = saída do programa). |
| 4 | Encaminhamento | 10% | RF18–RF20 | `forwarding.py` | Testes unitários com envio simulado; logs "encaminhado → próximo salto, TTL"; demo `msg` multi-salto. |
| 5 | ICMP | 15% | RF18–RF21, RF23 (ping) | `forwarding.py` + `cli.py` | Testes unitários (TTL→0 gera 11, sem rota gera 3, erro não gera erro, eco); demo `ping` TTL 1..N (cada salto responde 11, destino responde 0), `ping` rede inexistente, timeout 2 s. |
| 6 | Observabilidade | 5% | RF22, RF24 | `log.py` (terminal + arquivo, timestamp ms) | Arquivo `logs/<endereço>.log` atualizado em tempo real; todos os 5 tipos de evento exigidos presentes. |
| 7 | Interoperabilidade | 10% | RNF01, RF03, RF04, todos | Parsing estrito na saída, tolerante só onde o enunciado permite | Teste com pacotes "no fio" exatamente como nos exemplos do enunciado; teste real com outro grupo **antes** da apresentação. |
| 8 | Relatório | 20% | Q1–Q6 | `docs/relatorio/` + capturas | Topologia de 5 roteadores em uma máquina; capturas `.pcapng`; logs com timestamps em ms para medir convergência. |

**Estratégia para nota 10**
1. Fidelidade literal ao enunciado (formatos e regras), validada por testes que usam os exemplos do próprio enunciado.
2. Código simples, comentado em português, com um dono por módulo → todos conseguem explicar (evita o zero da regra de IA). Sessões de revisão cruzada obrigatórias.
3. Logs ricos e com timestamp em ms → servem ao critério 6 e às evidências do relatório (Q2, Q3).
4. Roteiro de demonstração ensaiado, com configs prontas e script de checagem.
5. Teste de interoperabilidade com outro grupo antes da apresentação.

---

## 4. Arquitetura e decisões técnicas (resumo)

Detalhes e interfaces em `IMPLEMENTATION_PLAN.md`; justificativas em `DECISIONS.md`.

- **Ambiente:** **VDI** (D24): VM Windows com Python 3.13 (comando `py`), acesso por https://vdi.pucrs.br;
  validado por um teste de fumaça (`docs/TESTE_VDI.md`); plano B = access point, com o mesmo código.
- **Endereços:** R1 William `10.6.1.1`, R2 Frederico `10.6.2.1`, R3 Gustavo `10.6.3.1` (D41).
- **Linguagem:** Python 3, **só biblioteca padrão** (`socket`, `threading`, `heapq`, `time`, `unittest`).
  Obrigatório na VDI. Código compatível com Python 3.8+.
- **Concorrência:** 3 threads — (1) recepção UDP (bloqueia em `recvfrom`), (2) temporizador
  (verifica a cada 0,5 s: HELLO 5 s, LSP 30 s, vizinho inativo 20 s, aging 90 s), (3) principal = CLI.
  **Um único lock** protege todo o estado do roteador. `ping` espera a resposta com
  `threading.Event` fora do lock.
- **Módulos:**

```
router.py       ponto de entrada + classe Router (estado, socket, threads, vizinhança, LSP/LSDB)
packets.py      formatação e parsing (estrito) dos 4 tipos de pacote; validação de endereços
config.py       leitura e validação do arquivo de configuração
dijkstra.py     Dijkstra puro: grafo -> {destino: (próximo salto, custo)}
forwarding.py   DADOS/ICMP: originar, receber, encaminhar, erros, ping pendente
cli.py          laço de comandos e formatação das saídas
log.py          logger thread-safe (terminal + arquivo, timestamp em ms)
```

- **Formato da config:** texto, uma diretiva por linha, `#` para comentários
  (`endereco`, `porta`, `vizinho <ip> <porta> <custo>`). Ver `IMPLEMENTATION_PLAN.md §3`.

---

## 5. Estrutura do repositório

**Estado:** em 2026-11-18 o repositório estava vazio; a F0 (2026-11-19) criou a estrutura abaixo
(`scripts/` e `docs/relatorio/` ainda não existem; os testes de cada módulo são criados pelos donos).

```
README.md                    execução + formato da config (entregável)
router.py, packets.py, config.py, dijkstra.py, forwarding.py, cli.py, log.py
configs/
  local5/r1.conf ... r5.conf topologia de 5 roteadores em 127.0.0.1 (relatório/testes)
  grupo/r1.conf ... r4.conf  rede do grupo para a apresentação (IPs a preencher)
tests/
  test_packets.py, test_config.py, test_dijkstra.py, test_router.py, test_forwarding.py,
  test_log.py, test_cli.py, test_interfaces.py
  integration_local.py       sobe 5 roteadores e verifica convergência, ping, queda
scripts/                     atalhos para subir a topologia local
logs/                        gerado em execução (no .gitignore)
docs/                        este conjunto de documentos + relatorio/
```

---

## 6. Funcionalidades: existentes e pendentes

F0 (2026-11-19): esqueleto pronto — os 7 módulos existem com a interface combinada e corpo
`NotImplementedError` indicando fase e dono; configs `local5` e `grupo`; `README.md`; `.gitignore`;
`tests/test_interfaces.py` (8 testes passando). Nenhuma funcionalidade do roteador implementada
ainda. Lista viva em `PROGRESS.md`.

---

## 7. Divisão de tarefas

**Atualização de 2026-11-23:** Frederico ficou indisponível até a apresentação por causa de uma prova. O que restava dele (teste de empate do Dijkstra e revisão da Q1) foi feito por William. Ele continua no grupo: precisa estar presente na apresentação e operar o R2 na própria VM.

**Redivisão de 2026-11-20:** o Leonardo saiu do grupo, que virou **trio** (William, Frederico,
Gustavo). Pedido de William: o relatório passa do Frederico para ele, e a parte do Leonardo é
repartida entre os dois que programam, com William ficando com mais (como já combinado, por ele
também fazer a parte do Gustavo). A divisão original está no histórico do git.

Princípio mantido: **um dono por arquivo** (evita conflito de merge e garante que cada um saiba
explicar o que escreveu); interfaces já fixadas.

| Responsável | Tarefas | Arquivos/módulos | Entregáveis | Dependências |
|---|---|---|---|---|
| **William** (núcleo, pacotes, integração, relatório, apresentação) | **Já entregue:** Router (vizinhança, LSP, inundação, sync, envelhecimento, tabela), logger, CLI, teste de integração, guia parte 1. **A fazer, nesta ordem:** (1) `packets.py` + `config.py` com testes — primeiro, porque destravam os testes do roteador, o `forwarding.py` do Frederico e os experimentos do relatório; (2) relatório inteiro: figura da `local5`, Q1–Q6, experimentos, capturas `.pcapng`, PDF (a tabela de iterações da Q1 vem da parte 3 do guia, do Frederico); (3) roteiro e condução da apresentação; guia parte 2 (packets/config); rede nas 3 VMs, interoperabilidade, README final, auditoria e `.zip`; revisão dos PRs | `router.py`, `log.py`, `cli.py`, `packets.py`, `config.py`, `configs/`, `tests/` (exceto dijkstra/forwarding), `docs/relatorio/`, `docs/APRESENTACAO.md`, `README.md` | Critérios 1, 2, 6, 7 e 8 (60%) + leitura/validação de pacotes usada por todos | Nenhuma: o que falta dele não espera ninguém |
| **Frederico** (cálculo de rotas e plano de dados) | **Já entregue:** Dijkstra, testes, guia parte 3. **A fazer:** `forwarding.py` + `tests/test_forwarding.py` (originar, entregar, encaminhar com TTL, ICMP 0/3/8/11, nunca erro sobre erro, `ping` com id, RTT e timeout de 2 s, textos do D40); guia parte 2 (forwarding); pendências da revisão do Dijkstra (teste de empate; "custos não negativos" no guia); revisar a Q1 do relatório e os PRs do William | `dijkstra.py`, `forwarding.py`, `tests/test_dijkstra.py`, `tests/test_forwarding.py` | Critérios 3, 4 e 5 (40%) | Interface já fixada (`route_for`, `is_local`, `send`, D40): pode começar já; os testes rodam quando o `packets.py` existir |
| **Gustavo** | Sem módulo de código neste trabalho (troca combinada: William faz a parte dele aqui, ele faz a de William em outro trabalho). Apresenta com o grupo, opera o roteador R3 e explica a vizinhança na reconvergência; estuda todo o código | — | Presença e domínio do código | Regra do enunciado: todos presentes e capazes de explicar qualquer parte |

**Por que assim:**
- **`packets.py` + `config.py` com o William:** são o bloqueio de tudo o que é dele (27 testes do
  roteador, teste de integração, experimentos do relatório). Fazendo ele mesmo, nada do que é dele
  espera outra pessoa. É o pedaço menor da parte do Leonardo.
- **`forwarding.py` com o Frederico:** é o maior bloco de código que falta (critérios 4 e 5, 25%),
  usa a tabela que o Dijkstra dele calcula e depende só de interfaces já fixadas, então ele pode
  começar já, em paralelo.
- **Carga:** William fica com o relatório (20%, grande) + pacotes/config + apresentação + integração
  (60% dos critérios sob responsabilidade dele); Frederico, com Dijkstra (pronto) + forwarding (40%).
  William com mais, como combinado.

**Integração e revisão:** branch por pessoa, PR pequeno para `main`; cada um revisa o PR do outro
(revisão cruzada também prepara para as perguntas). Pontos de integração ao fim de cada
fase (ver `IMPLEMENTATION_PLAN.md §6`).

---

## 8. Ordem de implementação (sem cronograma: por demanda, nesta ordem)

| Fase | Conteúdo | Responsáveis |
|---|---|---|
| F0 | Esqueleto, interfaces (stubs), formato da config, `.gitignore`, estrutura de testes; teste de fumaça da VDI | William (+1 integrante no teste de fumaça) |
| F1 | `packets.py` + `config.py`; `dijkstra.py` ✅; `log.py` ✅; Router base + vizinhança ✅ | William (packets/config, desde 2026-11-20); Frederico; William; William |
| F2 | LSP/LSDB/inundação/sync/aging ✅; `forwarding.py` + ping; `cli.py` ✅ | William; Frederico (desde 2026-11-20); William |
| F3 | Integração local com 5 roteadores; teste de integração; correções | Todos (William coordena) |
| F4 | Rede do grupo nas 3 VMs; interoperabilidade com outro grupo da VDI; capturas | Todos |
| F5 | Relatório, README, `.zip`; roteiro e ensaio da apresentação; auditoria final | William (relatório, apresentação, auditoria); ensaio com todos |

---

## 9. Estratégia de testes (resumo)

- **Unitários** (`unittest`, sem dependências): parsing/formatação com os exemplos do enunciado e
  casos malformados; config; Dijkstra (grafos conhecidos, empate, inalcançável, aresta só de ida);
  regras de recebimento de LSP e aging; decisões de encaminhamento com envio simulado.
- **Integração local:** 5 roteadores em `127.0.0.1` (portas 6001–6005) dirigidos por stdin:
  convergência, `tabela` esperada, `ping` TTL crescente, rede inexistente, queda e reinício,
  injeção de pacote malformado e de par desconhecido.
- **Manual/real:** várias máquinas no ambiente escolhido; Wireshark (`udp portrange 6000-6010`);
  interoperabilidade com outro grupo.

---

## 10. Dúvidas abertas e riscos

Resolvidas em 2026-11-19: ambiente = VDI (D24); G = 6 conferido no Moodle (D25); sem cronograma
(D28); integrantes (trio desde 2026-11-20): William, Frederico e Gustavo (D41); interpretações delegadas com a
regra de desempate (D05–D36); revisão geral do plano contra o enunciado (fim de `DECISIONS.md`).

Ainda abertas:
1. Teste de fumaça da VDI: parte A feita (Windows, Python 3.13, código roda); falta a parte B (VMs de
   contas diferentes se alcançam por UDP?), com o Gustavo.
2. Registrar a data de apresentação no Moodle (e o ambiente, se pedir). Integrantes já atualizados
   (trio) e professor avisado em 2026-11-21.

Riscos principais:
| Risco | Impacto | Mitigação |
|---|---|---|
| Integrante não explicar código (regra de IA) | **Nota zero** | Código simples e comentado; dono por módulo; revisão cruzada; ensaio de perguntas |
| Incompatibilidade com outro grupo | Perde critério 7 (10%) | Formatos literais; testes com exemplos do enunciado; teste real antecipado |
| Carga maior com 2 pessoas programando | Atraso no relatório (20%) ou no forwarding (25%) | Ordem definida na §7: `packets.py`/`config.py` primeiro; forwarding em paralelo; relatório e roteiro depois do código pronto e testado nas VMs (escolha do William) |
| Gustavo (que não escreve código neste trabalho) não saber explicar uma parte | Se ele não souber explicar o código questionado → **nota zero** para o trabalho | Incluí-lo nas revisões de PR e no ensaio de perguntas; ele estuda todos os módulos, não só a vizinhança |
| VDI indisponível / VMs não se alcançam | Rede não sobe | Teste de fumaça na F0; plano B access point (mesmo código) |
| IP da VM muda / várias interfaces | Rede não sobe na apresentação | Config fácil de editar; checklist pré-apresentação; bind em `0.0.0.0` |
| Versão do Python na VDI desconhecida | Não executa | Código compatível com 3.8+; conferir no teste de fumaça |
| Condições de corrida entre threads | Bugs intermitentes | Um único lock para todo o estado; testes de integração repetidos |
| Logs poluindo o terminal na demo | Demo confusa | Logs compactos (D29): 1 linha por recálculo, tabela só quando muda, HELLO só no arquivo (D34) |
| Entrega após o prazo (antes da 1ª aula de apresentação de qualquer grupo) | Trabalho não aceito | Checklist do plano §10 |
| Roteador reiniciado rápido demais (< 20 s) não recebe sincronização | `tabela` incompleta por até 30 s na demo | Reiniciar só depois de os vizinhos o marcarem inativo (plano §10) |
