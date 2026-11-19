# Enunciado (transcrição fiel dos prints do professor)

> Fonte: 7 prints enviados por William em 2026-11-18. Este arquivo é a **fonte de verdade** dos
> requisitos. Não editar o conteúdo; em caso de dúvida, comparar com os prints originais.
> Nenhum trecho estava ilegível. O item 2 do relatório aparece cortado entre o print 5 e o
> print 6, mas o texto continua no print 6 e foi reunido abaixo.

---

## Trabalho Final -- Roteador de estado de enlace sobre UDP

O trabalho consiste em implementar um **roteador de estado de enlace**, inspirado no OSPF, executando como uma aplicação sobre UDP. Cada integrante do grupo executa uma instância do roteador em sua máquina, e as instâncias formam juntas uma **rede virtual** sobre uma rede local real: as máquinas virtuais da VDI ou notebooks conectados a um access point (ver Ambiente de execução).

Cada roteador descobre seus vizinhos por meio de mensagens **HELLO**, gera e **inunda LSPs** (*Link State Packets*), monta a base de estados de enlace (LSDB) com a topologia completa da rede virtual e calcula sua tabela de roteamento com o **algoritmo de Dijkstra**. Sobre essa tabela, o roteador **encaminha datagramas** com controle de **TTL** e implementa um subconjunto do **ICMP**: `ping`, tempo excedido e destino inalcançável.

> **Atenção:** o formato dos pacotes e as regras de processamento devem ser seguidos fielmente. Durante a apresentação, a rede do grupo será **conectada à rede de outro grupo**, e os roteadores das duas implementações devem funcionar juntos.

---

## Endereçamento virtual

Cada grupo no Moodle recebe um número **G**, e cada roteador do grupo deve definir um número **R** (1, 2, 3...). O roteador R do grupo G:

- tem o endereço virtual **`10.G.R.1`**;
- é responsável pela rede **`10.G.R.0/24`**: qualquer datagrama destinado a um endereço dessa rede é entregue a esse roteador.

Exemplo: no grupo 7, os endereços virtuais dos roteadores são `10.7.1.1`, `10.7.2.1`, `10.7.3.1` e `10.7.4.1`. Com isso, os endereços virtuais continuam únicos quando as redes de dois grupos são conectadas.

Os endereços virtuais existem apenas dentro do trabalho. A comunicação real entre as máquinas usa os endereços IP reais delas na rede local.

---

## Vizinhos, enlaces e arquivo de configuração

Cada roteador conhece apenas seus **vizinhos**, isto é, os roteadores com os quais tem um **enlace** direto. Essa informação vem de um **arquivo de configuração**, lido ao iniciar o roteador. O formato do arquivo fica a critério do grupo, desde que contenha:

- o **endereço virtual** do roteador (`10.G.R.1`);
- a **porta UDP local** em que o roteador envia e recebe pacotes (padrão: **6000**);
- a lista de **vizinhos**, cada um com **endereço IP real**, **porta UDP** e **custo do enlace** (inteiro positivo).

Um enlace existe quando os dois roteadores listam um ao outro como vizinho, e os dois lados devem configurar o mesmo custo. As rotas escolhidas são as de menor soma de custos.

O arquivo diz apenas onde cada vizinho *pode* estar. Se ele está de fato em funcionamento, o roteador descobre pelas mensagens HELLO, descritas a seguir.

---

## Funcionamento do roteador

Esta seção descreve o comportamento do roteador. O formato exato de cada pacote está em Formato dos pacotes.

### Vizinhança

O HELLO (formato) tem três funções:

1. **Indicar que o vizinho configurado está de fato em funcionamento.** Um vizinho em funcionamento é chamado de **ativo**, e somente vizinhos ativos entram no LSP (descrito na próxima seção).
2. **Detectar a falha de um vizinho.** O UDP não tem conexão, e a ausência de HELLO é a única indicação de que o vizinho caiu.
3. **Informar o endereço virtual do vizinho**, associando-o ao par (IP real, porta) de onde o HELLO veio.

Regras:

- O roteador envia **HELLO a cada 5 segundos** para todos os vizinhos configurados (IP real e porta do arquivo de configuração).
- Um vizinho passa a ser **ativo** quando o primeiro HELLO dele é recebido. O roteador associa o **endereço virtual** informado no HELLO ao par (**IP real, porta**) de onde o pacote veio; essa associação é usada para enviar pacotes a esse vizinho.
- Um vizinho que fica **20 segundos** (4 períodos) sem enviar HELLO é considerado **inativo**.

Toda mudança na lista de vizinhos ativos (entrada ou saída) gera **imediatamente** um novo LSP.

### LSPs e inundação

O LSP (formato) descreve os vizinhos ativos de um roteador e o custo de cada enlace. Inundando os LSPs, todos os roteadores passam a ter a mesma LSDB, isto é, a topologia completa da rede virtual.

#### Geração

O roteador gera um novo LSP próprio:

- quando um vizinho se torna ativo ou inativo;
- periodicamente, a cada **30 segundos** (renovação), mesmo sem mudança.

Cada roteador mantém **seu próprio número de sequência**, usado apenas nos LSPs que ele gera; ao reenviar o LSP de outro roteador, o número de sequência não é alterado. O número do primeiro LSP é o **horário atual em segundos** (Unix time), e cada novo LSP incrementa o número em 1. Com isso, um roteador que é reiniciado continua gerando números maiores do que os que os outros roteadores já conhecem.

O LSP próprio é enviado a todos os vizinhos ativos e armazenado na própria LSDB.

#### Recebimento

Ao receber um LSP do vizinho V:

1. Se a origem do LSP é o próprio roteador: descartar.
2. Se a LSDB já possui um LSP dessa origem com número de sequência **maior ou igual**: descartar (é uma cópia ou um LSP antigo).
3. Caso contrário: substituir o LSP armazenado, **reenviar uma cópia a todos os vizinhos ativos, exceto V**, e recalcular a tabela de roteamento.

#### Sincronização com novo vizinho

Quando um vizinho se torna ativo, além do novo LSP próprio, o roteador envia **a ele** uma cópia de **todos os LSPs da sua LSDB**. Sem isso, um roteador que entra na rede só conheceria os outros roteadores na próxima renovação.

#### Envelhecimento

Um LSP de outro roteador que não é renovado por **90 segundos** é removido da LSDB, e a tabela é recalculada. Isso remove da LSDB os roteadores que saíram da rede.

### Cálculo da tabela de roteamento

A LSDB define um grafo: cada LSP de origem O contém as arestas de O para cada vizinho listado, com o custo indicado. O roteador executa o **algoritmo de Dijkstra** a partir de si mesmo e, para cada roteador alcançável R, registra na tabela:

| Rede de destino | Próximo salto | Custo |
|---|---|---|
| rede de R (ex.: `10.G.R.0/24`) | endereço virtual do vizinho pelo qual começa o caminho de menor custo | soma dos custos |

A tabela é recalculada sempre que a LSDB muda. Em caso de empate, qualquer caminho de custo mínimo é aceito.

### Encaminhamento

O roteador encaminha dois tipos de pacote: **DADOS** (formato), com uma mensagem de texto, e **ICMP** (formato), com mensagens de controle. Ambos têm endereço virtual de origem e de destino, **TTL** (iniciado em 16 por quem cria o pacote) e um **id** que associa respostas a pedidos.

#### Tipos de mensagem ICMP

| Tipo | Mensagem | Gerada por |
|---|---|---|
| 8 | Pedido de eco | Origem do `ping` |
| 0 | Resposta de eco | Destino do pedido de eco |
| 11 | Tempo excedido | Roteador em que o TTL chega a 0 |
| 3 | Destino inalcançável | Roteador sem rota para o destino |

#### Ao originar um pacote (DADOS ou ICMP)

Consultar a tabela. Se não houver rota para a rede do destino, informar **destino inalcançável** ao usuário, sem enviar nada. Caso contrário, enviar com o TTL inicial (16, ou o valor indicado no comando `ping`) ao próximo salto, isto é, ao par (IP real, porta) associado ao endereço virtual do próximo salto.

#### Ao receber um pacote DADOS ou ICMP

1. **Destino na própria rede** (`10.G.R.0/24`): o pacote é entregue ao próprio roteador, que representa todos os endereços da sua rede (não há hosts reais: `10.7.1.1` e `10.7.1.50` são ambos atendidos pelo roteador `10.7.1.1`).
2. `DADOS`: exibir a origem, o destino e a mensagem.
3. `ICMP` tipo 8: responder com tipo 0 para a origem, com o mesmo id. A origem da resposta é o **endereço de destino do pedido** (quem foi "pingado").
4. `ICMP` tipos 0, 11 ou 3: exibir o resultado ao usuário.
5. **Destino em outra rede**:
6. Decrementar o TTL. Se chegar a 0, descartar e enviar **ICMP tipo 11** para a origem.
7. Consultar a tabela. Se não houver rota, descartar e enviar **ICMP tipo 3** para a origem.
8. Caso contrário, encaminhar ao próximo salto (IP real e porta associados ao seu endereço virtual) com o novo TTL.

**Mensagens de erro (tipos 11 e 3) geradas pelo roteador** usam o endereço virtual do próprio roteador como origem, TTL 16 e o id do pacote que causou a mensagem.

> **Atenção:** assim como no ICMP, **nunca** se gera mensagem de erro (tipos 11 ou 3) em resposta a outra mensagem de erro.

---

## Interface com o usuário

O roteador é um único programa, executado em um terminal. Enquanto executa, ele lê comandos digitados nesse mesmo terminal e exibe nele os resultados e os logs. Nos comandos, `<destino>` é sempre um **endereço virtual**.

| Comando | Ação |
|---|---|
| `tabela` | Exibe a tabela de roteamento (rede, próximo salto, custo) |
| `lsdb` | Exibe a LSDB (origem, número de sequência, vizinhos e custos) |
| `vizinhos` | Exibe os vizinhos ativos (endereço virtual, IP real e porta) |
| `msg <destino> <texto>` | Envia um pacote de dados |
| `ping <destino> [TTL]` | Envia um pedido de eco com o TTL indicado (padrão: 16) e exibe a resposta recebida (eco, tempo excedido ou destino inalcançável), quem a enviou e o RTT, ou timeout após 2 s |

Além disso, o roteador deve salvar em logs em tempo real: vizinhos que ficaram ativos/inativos, LSPs novos recebidos, recálculos da tabela, pacotes encaminhados (com o próximo salto e o TTL) e mensagens ICMP geradas.

---

## Especificação técnica

### Ambiente de execução

Cada grupo escolhe **um** dos ambientes abaixo, e todos os roteadores do grupo executam nele:

- **VDI:** cada integrante executa seu roteador em sua máquina virtual de redes (somente Python);
- **Access point:** cada integrante executa seu roteador em seu notebook, conectado a um access point sem internet levado pelo professor na apresentação (qualquer linguagem de programação).

Dicas:

- O endereço IP real de cada máquina pode mudar a cada conexão (DHCP). Mantenha um arquivo de configuração fácil de editar.
- Em computadores pessoais, pode ser necessário liberar a porta UDP do roteador no **firewall**.
- Grupos que usarão o access point podem testar antes em qualquer rede Wi-Fi compartilhada (em casa ou com o celular como ponto de acesso).

### Regras gerais de comunicação

- Toda comunicação usa **UDP**, com mensagens em **texto ASCII** e campos separados por `:`.
- O roteador deve **enviar e receber pelo mesmo socket**, ligado à porta configurada. Assim, a porta UDP de origem dos pacotes enviados é a própria porta do roteador, e o vizinho consegue identificá-lo.
- Pacotes vindos de um par (IP real, porta) que **não está** na lista de vizinhos são descartados.
- Pacotes **malformados** (tipo desconhecido, número errado de campos, valores não numéricos) são descartados **sem derrubar o roteador**.

### Formato dos pacotes

#### HELLO

```
HELLO:<endereço virtual>
```
Exemplo: `HELLO:10.3.1.1`

#### LSP

```
LSP:<origem>:<número de sequência>:<vizinho>=<custo>;<vizinho>=<custo>;...
```
Exemplo: `LSP:10.3.1.1:1767712000:10.3.2.1=1;10.3.4.1=3`

A lista contém os **vizinhos ativos** do roteador de origem (endereços virtuais), com o custo configurado para cada enlace. Um roteador sem vizinhos ativos envia a lista vazia: `LSP:10.3.1.1:1767712001:`.

#### Dados

```
DADOS:<origem>:<destino>:<TTL>:<id>:<mensagem>
```
Exemplo: `DADOS:10.3.1.1:10.3.4.1:16:0:Oi pessoal!`

#### ICMP

```
ICMP:<origem>:<destino>:<TTL>:<id>:<tipo>
```
Exemplo: `ICMP:10.3.1.1:10.3.4.1:16:42:8`

O campo **tipo** segue a tabela de tipos de mensagem ICMP.

#### Campos

- **origem/destino**: endereços virtuais.
- **TTL**: iniciado em **16** por quem cria o pacote.
- **id**: identificador escolhido pela origem para associar respostas a pedidos (ex.: um contador). Respostas de eco e mensagens de erro **copiam o id** do pacote que as provocou. Em pacotes de dados, o id pode ser 0.

> **Atenção:** a mensagem não pode conter dois pontos (`:`) nem caracteres fora do ASCII (sem acentos). Pacotes com esses caracteres são malformados.

---

## Relatório

O relatório deve responder às questões abaixo, com evidências (logs, saídas dos comandos, capturas do Wireshark). Os experimentos podem ser feitos em uma única máquina, executando vários roteadores em portas diferentes.

Montar uma topologia de teste com **pelo menos 5 roteadores** e enlaces de custos diferentes, incluindo pelo menos um caminho alternativo. Incluir a figura da topologia com os custos.

1. **Dijkstra:** para um dos roteadores, apresentar a LSDB e a execução do algoritmo de Dijkstra passo a passo (tabela de iterações, como na aula), comparando o resultado com a tabela exibida pelo programa.
2. **Inundação:** contar, a partir de uma captura do Wireshark ou dos logs, quantos pacotes LSP circulam na rede após **uma única mudança** (a queda de um vizinho). Quantos foram descartados como cópias? Analise e compare com o que um protocolo de vetor distância enviaria na mesma situação.
3. **Convergência:** derrubar um roteador que esteja no caminho entre dois outros e medir o tempo até a rota ser recalculada. Quanto desse tempo corresponde à detecção da falha e quanto à inundação e ao recálculo? Relacione com os temporizadores do HELLO.
4. **Números de sequência:** por que o LSP precisa de um número de sequência? O que aconteceria se um roteador reiniciado voltasse a numerar seus LSPs a partir de 0?
5. **Confiabilidade:** os LSPs são enviados por UDP e não têm confirmação. O que acontece se um LSP for perdido? Qual mecanismo da especificação recupera a LSDB?
6. **TTL:** se todos os roteadores calculam as rotas sobre a mesma topologia, por que ainda é necessário o TTL? Descreva uma situação, durante a convergência, em que um pacote poderia circular em laço.

---

## Apresentação

As apresentações ocorrem em **3 dias**, com cerca de 5 grupos por dia. Os grupos de cada dia são divididos pelo professor em **duplas de grupos** (ou um trio de grupos, se o número for ímpar), com cerca de 30 minutos por dupla. As duplas são formadas por grupos do **mesmo ambiente de execução** (VDI com VDI, access point com access point).

**Rede do grupo:** cada integrante executa um roteador em sua própria máquina, no ambiente escolhido pelo grupo (4 roteadores nos quartetos, 3 nos trios), com enlaces de custos diferentes e pelo menos um caminho alternativo. A rede deve estar **montada e funcionando** no início do horário da dupla.

**Cada grupo (~10 min):**

1. Exibe `vizinhos`, `lsdb` e `tabela` em cada roteador, conferindo com a topologia.
2. Executa `ping` com TTL 1, 2, 3... até o roteador mais distante, mostrando cada roteador do caminho, e envia uma `msg`.
3. Executa `ping` para uma rede inexistente.
4. O professor derruba um roteador ou enlace; o grupo mostra a reconvergência e repete o `ping` com TTL crescente, mostrando o novo caminho. O roteador derrubado é reiniciado em seguida.
5. Perguntas sobre o código.

**Interoperabilidade (~5 min, ao final da dupla):** os dois grupos criam um enlace entre um roteador de cada rede (uma linha a mais no arquivo de configuração de cada lado) e mostram:

1. a `lsdb` e a `tabela` com os roteadores do outro grupo;
2. `ping` (com TTL crescente) e `msg` atravessando as duas redes;
3. a reconvergência quando o professor derruba o enlace entre os grupos.

Recomenda-se testar com outros grupos antes da apresentação.

Todos os integrantes devem estar presentes e ser capazes de explicar qualquer parte do código.

> **SOBRE O USO DE IA:** o uso de IA é permitido, mas código que o integrante questionado não consiga explicar não será considerado de autoria do grupo, e o trabalho receberá nota **zero**, independentemente de funcionar.

---

## Avaliação

**Os itens 1 a 6 são avaliados na rede do grupo durante a apresentação; o item 7, na conexão com a rede do outro grupo.**

| # | Critério | Descrição | Peso |
|---|---|---|---|
| 1 | **Vizinhança** | HELLO periódico, detecção de vizinho ativo/inativo | 5% |
| 2 | **LSPs e inundação** | Geração, número de sequência, inundação, descarte de cópias, sincronização com novo vizinho, envelhecimento | 20% |
| 3 | **Tabela de roteamento** | Dijkstra correto sobre a LSDB, recálculo após mudanças | 15% |
| 4 | **Encaminhamento** | Entrega e encaminhamento de dados com decremento de TTL | 10% |
| 5 | **ICMP** | `ping` com TTL, resposta de eco, tempo excedido, destino inalcançável | 15% |
| 6 | **Observabilidade** | Logs em tempo real dos eventos | 5% |
| 7 | **Interoperabilidade** | Rede conectada à do outro grupo: LSDB, rotas, `ping`/`msg` e reconvergência entre as duas implementações | 10% |
| 8 | **Relatório** | Experimentos e questões | 20% |
| | **Total** | | **100%** |

---

## Regras Gerais

**Grupos: 4 componentes**. Trios serão aceitos apenas para fechar a divisão da turma (ex.: com 58 alunos, 13 quartetos e 2 trios). Informar no Moodle os integrantes e data de apresentação.

**Linguagem:** livre, usando a API de sockets UDP diretamente. O algoritmo de Dijkstra deve ser **implementado pelo grupo**: não é permitido usar bibliotecas de grafos ou de roteamento (ex.: `networkx`, `scipy.sparse.csgraph`, JGraphT). Estruturas de dados da biblioteca padrão, como filas de prioridade (`heapq`, `PriorityQueue`), são permitidas.

**Data de entrega:** todos os grupos antes do início da primeira aula de apresentação
**Datas de apresentação:** conferir no Moodle

Obs.: todos os participantes do grupo devem estar presentes para a apresentação.

**Entrega final** (arquivo `.zip`, por um integrante do grupo):

- Código-fonte (sem binários ou arquivos de build);
- `README` com instruções de execução e o formato do arquivo de configuração;
- Relatório em PDF;
- Capturas (`.pcapng`) usadas no relatório.

**IMPORTANTE**: Não serão aceitos trabalhos entregues fora do prazo. Trabalhos que não compilam ou que não executam não serão avaliados. Todos os trabalhos serão analisados e comparados. Caso seja identificada cópia de trabalhos, todos os trabalhos envolvidos receberão nota ZERO.
