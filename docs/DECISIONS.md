# DECISIONS — Decisões técnicas e interpretações do enunciado

Status: **Confirmada** · **Pendente (grupo)** (precisa de resposta do grupo) · **Revogada**.
Ao mudar uma decisão, não apague: marque como Revogada e crie outra.

Tipo: **T** = escolha técnica livre · **I** = interpretação de ponto que o enunciado não detalha ·
**L** = leitura literal do enunciado registrada para não haver dúvida depois.

**Regra de desempate (definida por William em 2026-11-19):** quando o enunciado não define algo,
escolher a opção que (1) cumpre literalmente o texto do professor e protege a interoperabilidade
e, entre as que cumprem, (2) é a **mais simples de implementar e de explicar** na apresentação.
Antes de decidir, estudar o ponto; nada de complexidade que não traga nota.
William delegou as decisões D01–D44 com essa regra; elas estão confirmadas.

| ID | Tipo | Decisão | Justificativa | Status |
|---|---|---|---|---|
| D01 | T | Python 3, apenas biblioteca padrão, compatível com 3.8+ | Obrigatório na VDI (D24); sem dependências para instalar | Confirmada |
| D02 | T | 3 threads (recepção, temporizador, CLI) e **um único lock** para todo o estado | Mais simples de explicar e de acertar do que `select`/asyncio; um lock elimina corridas | Confirmada |
| D03 | T | Config em texto: `endereco`, `porta` (padrão 6000), `vizinho <ip> <porta> <custo>`, `#` comentário | Fácil de editar no dia; interop = 1 linha a mais | Confirmada |
| D04 | T | Socket ligado a `0.0.0.0:<porta>` | Recebe em qualquer interface; porta de origem dos envios = porta do roteador (RF02) | Confirmada |
| D05 | I | Pacotes (LSP, DADOS, ICMP) de vizinho **configurado** mas ainda sem HELLO são **aceitos** | O enunciado só manda descartar pares fora da lista de configuração; é também o teste mais simples (um `if`) | Confirmada |
| D06 | I | O "vizinho V" que enviou o LSP é identificado pelo par (IP, porta) de origem; o reenvio exclui esse par | Funciona mesmo se V ainda não mandou HELLO; não precisa de tabela extra | Confirmada |
| D07 | L | Grafo **dirigido** exatamente como nos LSPs (aresta O→vizinho só do LSP de O); sem checagem de bidirecionalidade. Nó que só aparece como vizinho em algum LSP também é destino | Texto: "cada LSP de origem O contém as arestas de O para cada vizinho listado"; é o Dijkstra "de aula", sem regra extra | Confirmada |
| D08 | I | A `tabela` **não** mostra a rede do próprio roteador | "para cada roteador alcançável R" a partir de si mesmo; a saída do Dijkstra já exclui a origem | Confirmada |
| D09 | I | `ping`/`msg` para endereço da **própria** rede: o pacote criado é passado direto à mesma função de "recebimento" (entrega local), sem ir à rede. Ping a si mesmo responde eco com RTT ≈ 0 | **Único caso que o texto não cobre** (a regra "ao originar" não fala da própria rede, e a própria rede não está na tabela). Seguimos a regra 1 do recebimento: "o pacote é entregue ao próprio roteador, que representa todos os endereços da sua rede". Não faz parte do roteiro da apresentação | Confirmada |
| D10 | L | Geram erro (11/3) em trânsito: DADOS, ICMP 8 e ICMP 0. Só ICMP 11 e 3 **não** geram erro | "nunca se gera mensagem de erro em resposta a outra mensagem de erro"; eco não é erro | Confirmada |
| D11 | L | Pacote criado pelo próprio roteador sem ser comando do usuário (resposta de eco 0, erros 11/3) e sem rota até o destino: não envia nada e registra em log | É a regra "ao originar" (sem rota → informar e não enviar); como não há usuário esperando, "informar" = log | Confirmada |
| D12 | I | Parsing **estrito** (tipo, nº de campos, dígitos, IPv4 válido, custo > 0, tipo ICMP ∈ {0,3,8,11}); **tolerante** só a `\n`/`\r\n` final do datagrama e a itens vazios na lista do LSP (ex.: `;` final). Na saída, sempre o formato exato | Estrito onde o enunciado define "malformado"; as 2 tolerâncias custam 1 linha cada e protegem o critério 7 (outra linguagem pode mandar `\n`) | Confirmada |
| D13 | L | Mensagem válida = só caracteres ASCII e sem `:` (exatamente o que o enunciado proíbe, nada além). A CLI recusa antes de enviar; no recebimento, o resto é malformado | "a mensagem não pode conter dois pontos nem caracteres fora do ASCII" | Confirmada |
| D14 | I | TTL em trânsito: decrementa; se resultado ≤ 0 → descarta + ICMP 11 | Um `<=` cobre também pacote que chega com TTL 0 de outra implementação | Confirmada |
| D15 | T | ~~Logs em arquivo e terminal com flag `--quiet`~~ | Substituída por D29 (flag desnecessária) | Revogada |
| D16 | I | ~~Gerar o 1º LSP na partida~~ | A partida **não** está entre os gatilhos de geração do enunciado. Substituída por D30 | Revogada |
| D17 | T | Temporizador com tick de 0,5 s (inatividade detectada entre 20 e 20,5 s) | Precisão suficiente para medir convergência (Q3) | Confirmada |
| D18 | I | `ping` bloqueia a CLI até a resposta ou 2 s. ICMP 0/11/3 sem ping pendente (atrasados) são exibidos como resultado | Regra 4: "exibir o resultado ao usuário" | Confirmada |
| D19 | T | id do `ping`: contador por roteador a partir de 1; DADOS com id 0 | Enunciado sugere contador e permite id 0 em DADOS | Confirmada |
| D20 | T | Único comando além dos 5 do enunciado: `sair` (encerra limpo; o enunciado manda reiniciar o roteador derrubado). Comando desconhecido mostra a lista dos comandos válidos. Sem `ajuda` | Extras não alteram nada do que é avaliado; mantido só o que é útil na demo | Confirmada |
| D21 | I | HELLO de par já ativo com endereço virtual diferente: atualiza a associação e gera novo LSP | Caso raro; tratado como mudança na lista de ativos (2 linhas) | Confirmada |
| D22 | L | Envelhecimento conta a partir do último LSP **aceito** daquela origem; LSP próprio nunca envelhece | "LSP de outro roteador que não é renovado por 90 s" | Confirmada |
| D23 | L | Vizinho que fica inativo **não** tem seu LSP apagado na hora; sai por substituição ou envelhecimento (90 s) | Só esses dois mecanismos existem no enunciado; sem arestas apontando para ele, deixa de ser alcançável | Confirmada |
| D24 | T | **Ambiente: VDI.** Plano B: access point (o código é o mesmo; só mudam IPs nas configs) | Ver análise abaixo | Confirmada (validar com o teste de fumaça) |
| D25 | L | **G = 6** → roteadores `10.6.R.1`, redes `10.6.R.0/24` | "Cada grupo no Moodle recebe um número G"; o exemplo do grupo 7 usa `10.7.R.1`. Número conferido no Moodle por William em 2026-11-19 | Confirmada |
| D26 | T | ~~Rastro das iterações do Dijkstra (`trace=True`)~~ | Removido: a Q1 pede a tabela de iterações feita "como na aula" (à mão) comparada com a `tabela` do programa; o rastro só aumentaria o código a explicar | Revogada |
| D27 | T | Numeração: R1 = William (`10.6.1.1`), R2 = Leonardo (`10.6.2.1`), R3 = Frederico (`10.6.3.1`), R4 = Gustavo (`10.6.4.1`) | Fixa endereços das configs da apresentação | Revogada (2026-11-20: Leonardo saiu; ver D41) |
| D28 | T | Sem cronograma com datas: execução por demanda, seguindo a **ordem** das fases F0–F5 | Pedido de William | Confirmada |
| D29 | T | Logs sempre no terminal **e** em `logs/<endereço>.log` (flush imediato), sem flags. **Todo** recálculo gera 1 linha de log; a tabela inteira só é logada quando muda; HELLO só no arquivo (D34) | Cumpre "salvar em logs em tempo real" os 5 eventos exigidos e "exibe nele ... os logs" | Confirmada |
| D30 | L | Não há LSP na partida. O LSP próprio é gerado só nos gatilhos do enunciado: vizinho ficou ativo/inativo, ou a cada 30 s (contados a partir da partida, mesmo sem vizinhos ativos). O 1º LSP usa seq = Unix time do momento em que é gerado; cada novo LSP faz seq + 1 | Texto: "gera um novo LSP próprio: quando um vizinho se torna ativo ou inativo; periodicamente, a cada 30 segundos" e "o número do primeiro LSP é o horário atual em segundos" | Confirmada |
| D32 | L | Renovação do LSP próprio em **período fixo** de 30 s contado desde a partida, independente dos LSPs gerados por mudança de vizinho | Texto: "periodicamente, a cada 30 segundos (renovação), mesmo sem mudança". Tão simples quanto zerar o contador a cada LSP, e mais fiel à palavra "periodicamente" | Confirmada |
| D33 | T | Laços de recepção e do temporizador protegidos por `try/except Exception` (loga `ERRO` e continua); `send()` captura `OSError` | "descartados sem derrubar o roteador": garante que nenhuma entrada inesperada ou erro de rede mata uma thread (no Windows, `recvfrom` pode lançar `ConnectionResetError`, relevante no plano B) | Confirmada |
| D34 | T | HELLO enviados/recebidos vão **só para o arquivo** de log (parâmetro `terminal=False` do logger) | O critério 1 avalia "HELLO periódico" e o terminal precisa ficar legível; o arquivo prova a periodicidade sem poluir a demo | Confirmada |
| D35 | T | Ao reenviar um LSP (inundação), usar `packets.encode(pkt)`: mesma origem, mesmo seq, mesma lista | Garante que só sai do nosso roteador o formato exato, mesmo se o LSP chegou com `\n` ou `;` final (D12). O seq não muda, como manda o texto | Confirmada |
| D36 | T | Topologias com custos **todos diferentes** e sem empate de caminho mínimo: `local5` = 1,4,2,7,3,5; `grupo` = 1,2,3,7 | "enlaces de custos diferentes" na leitura mais forte; Q1 com resposta única | Confirmada |
| D37 | T | O arquivo de log é aberto para **acrescentar**: ao reiniciar o roteador, o histórico anterior continua no mesmo arquivo | Mostra antes e depois de um reinício no mesmo log (Q3 do relatório e demo de reinício); não exige código extra | Confirmada |
| D38 | T | A CLI captura exceção de um comando, mostra `Erro ao executar o comando: ...` e continua lendo | Um erro num comando não pode encerrar o roteador no meio da demo; mesmo espírito da D33 | Confirmada |
| D39 | T | Tudo o que o programa mostra na tela ou grava no log (mensagens, cabeçalhos, textos de log) é **ASCII, sem acentos**. Comentários e docstrings podem ter acento | Teste real: com a saída do terminal em ASCII, o `print` de "Próximo" derrubava a CLI (`UnicodeEncodeError`). Em locale C o Python 3.7+ já resolve, mas sem acento não há risco em nenhum terminal; o protocolo já é ASCII. Garantido por `tests/test_cli.py::TestSaidaAscii` | Confirmada |
| D40 | T | Textos que o `forwarding.py` mostra ao usuário têm começo fixo (ex.: `Resposta de eco de <origem>`, `Tempo excedido informado por <origem>`, `Destino inalcancavel: sem rota para ...`, `Mensagem de <origem> para <destino>: <texto>`); lista completa no topo do `forwarding.py` | O teste de integração confere esses textos; fixar agora evita retrabalho. Cumpre o enunciado: ping mostra tipo da resposta, quem enviou e RTT; DADOS mostra origem, destino e mensagem. Frederico (dono do `forwarding.py` desde 2026-11-20) pode propor outra redação, desde que atualize o contrato e o teste | Confirmada |
| D41 | T | Grupo virou **trio** (2026-11-20). Numeração: R1 = William (`10.6.1.1`), R2 = Frederico (`10.6.2.1`), R3 = Gustavo (`10.6.3.1`). Apresentação com **3 roteadores** | Enunciado: "4 roteadores nos quartetos, 3 nos trios". Números seguidos, sem buraco, ficam mais fáceis de explicar | Confirmada |
| D42 | T | Topologia `grupo` do trio: triângulo R1–R2 = 1, R2–R3 = 2, R1–R3 = 5 (substitui o anel de 4 da D36; a `local5` não muda) | Custos todos diferentes, sem empate, e com caminho alternativo: R1→R3 vai por R2 (3) em vez do enlace direto (5), então `ping` com TTL 1 e 2 mostra R2 e depois R3; derrubando R2, R1→R3 usa o enlace direto | Confirmada |
| D43 | T | `config.py`, detalhes do formato D03: diretiva desconhecida, `endereco`/`porta` repetidos ou com nº errado de argumentos são **erro** (com nº da linha); arquivo lido como UTF-8 (comentários podem ter acento); o aviso de endereço fora de `10.G.R.1` é um `print` e o roteador inicia. A validação de número e de IPv4 reusa `packets.so_digitos`/`packets.is_virtual_addr` (o `cli.py` também passou a usar `packets.so_digitos`) | O formato é "a critério do grupo". Erro claro no início é mais simples de explicar do que adivinhar qual linha vale; uma só função de validação para pacote, config e CLI | Confirmada |
| D31 | L | Sincronização: quando um vizinho fica ativo, primeiro gera o novo LSP próprio (enviado a todos os ativos), depois envia ao novo vizinho uma cópia de **todos** os LSPs da LSDB, inclusive o próprio | Texto: "além do novo LSP próprio, o roteador envia a ele uma cópia de todos os LSPs da sua LSDB". A cópia repetida do LSP próprio é descartada pelo vizinho (regra 2) | Confirmada |
| D44 | T | Na thread de recepção, `ConnectionResetError` do `recvfrom` é ignorado sem log (`continue`); qualquer outro erro continua virando `[ERRO]` (D33) | A VM da VDI é Windows. No Windows, um datagrama enviado a uma porta fechada (vizinho que caiu) faz o **próximo** `recvfrom` levantar `ConnectionResetError` (WSAECONNRESET). Não é pacote recebido nem falha nossa; sem isto, cada HELLO ao vizinho caído geraria uma linha `[ERRO]` na tela durante a demonstração de queda. A detecção de queda não muda (20 s sem HELLO). O desligamento disso via `ioctl` não existe no `socket` do Python, então um `except` de 1 linha é o mais simples | Confirmada |

## Análise do ambiente (D24)

O código será Python puro nos dois casos, então a linguagem não decide. O que decide é o risco
operacional no dia e a facilidade de testar antes.

| Aspecto | VDI | Access point |
|---|---|---|
| Linguagem | Só Python (já é a nossa escolha) | Qualquer |
| Máquinas | VMs padronizadas "de redes", preparadas pela disciplina | 4 notebooks pessoais, SOs diferentes; todos precisam ter notebook |
| Firewall | Sem firewall pessoal para liberar (VM do laboratório) | Windows bloqueia UDP de entrada por padrão (rede "Pública"); macOS pode perguntar; cada um libera no seu |
| IPs | Rede do laboratório | DHCP do AP do professor: IPs só são conhecidos na hora → editar configs durante a apresentação |
| Testar antes, juntos | Cada um acessa a sua VM de onde estiver; as VMs se enxergam por definição do enunciado | Precisa estar fisicamente na mesma rede Wi-Fi (hotspot); hotspots às vezes isolam clientes |
| Testar com outros grupos | Remoto, entre VMs | Precisa encontrar o outro grupo presencialmente |
| Riscos próprios | Versão do Python da VM desconhecida; instabilidade/indisponibilidade da VDI; colocar o código na VM | Firewall, DHCP, isolamento de clientes, bateria/notebook de alguém falhar |

**Escolha: VDI** — menos peças fora do nosso controle no dia e possibilidade de testar tudo, inclusive
interop, sem se reunir. Os riscos da VDI são verificáveis cedo com o teste de fumaça abaixo; se ele
falhar, migramos para o access point sem mudar uma linha de código.

Conferido na VDI em 2026-11-21 (parte A de `docs/TESTE_VDI.md`): portal https://vdi.pucrs.br
(Omnissa Horizon, no navegador); a VM de redes é **Windows** com **Python 3.13.0** (comando `py`);
o código roda inteiro lá (testes unitários e integração com 5 processos); Wireshark instalado,
captura na `Ethernet0` e na loopback; código levado pelo ZIP do GitHub baixado no navegador da VM.
Ainda não verificado: se as VMs de integrantes diferentes se alcançam por UDP (parte B, com o
Gustavo) e se a VM guarda os arquivos entre um login e outro.
Verificar também se o Moodle pede para registrar o ambiente escolhido (as duplas são formadas por ambiente).

### Teste de fumaça da VDI (5 minutos, 2 integrantes, antes de F1 terminar)

Versão completa, passo a passo, com os roteadores de verdade e o que fazer se der errado: `docs/TESTE_VDI.md`.

Em cada VM: `python3 --version` (precisa ser ≥ 3.8) e anotar o IP (`ip addr` ou `hostname -I`).

VM A (recebe):
```bash
python3 -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('0.0.0.0', 6000)); print(s.recvfrom(100))"
```
VM B (envia), trocando `IP_DA_VM_A`:
```bash
python3 -c "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'HELLO:10.6.2.1', ('IP_DA_VM_A', 6000))"
```
Passou se a VM A imprimir `(b'HELLO:10.6.2.1', ('<IP da VM B>', <porta>))`. Repetir no sentido inverso.

## Verificação literal contra o enunciado (2026-11-19)

Cada decisão foi relida contra `ENUNCIADO.md`. Resultado:

| Situação | Decisões |
|---|---|
| Seguem o texto literalmente (L) | D07, D10, D11, D13, D22, D23, D25, D30, D31, D32 |
| Escolhas técnicas onde o enunciado deixa livre ("formato a critério do grupo", linguagem livre etc.) | D01–D04, D17, D19, D24, D27–D29, D33–D36, D43, D44 |
| Interpretações que **cumprem** o texto e só preenchem um detalhe que ele não descreve | D05 ("lista de vizinhos" = a do arquivo de configuração), D06 (V = par de origem do LSP), D08 (a tabela lista "cada roteador alcançável R", e o próprio não tem próximo salto), D12 (tolerância a `\n` final e `;` final: não muda nº de campos nem números, nunca é enviada por nós), D14 (`<= 0` cobre "chegar a 0"), D18 (respostas atrasadas: regra 4 "exibir ao usuário"), D21 (associação refeita a cada HELLO) |
| Caso **não coberto** pelo texto | D09 (ping/msg para a própria rede) — fora do roteiro da apresentação |
| Corrigidas nesta verificação | D16 → D30 (não gerar LSP na partida); sincronização → D31 (enviar **todos** os LSPs, sem filtrar o próprio); D20 (removido `ajuda`) |

## Revisão geral do plano contra o enunciado (2026-11-19, a pedido de William)

Todo o enunciado foi percorrido regra por regra contra o plano. Ajustes feitos:

| Achado | Por que importa | Correção |
|---|---|---|
| Inundação reenviava o datagrama original | Se chegasse com `\n` final (tolerado), sairia do nosso roteador fora do formato | D35 |
| Renovação "30 s desde o último LSP" | O texto diz "periodicamente, a cada 30 segundos" | D32 |
| Mensagem exigia ASCII "imprimível" | Mais restrito que o enunciado: poderia descartar pacote válido de outro grupo | D13 corrigida |
| HELLO não aparecia em lugar nenhum | Critério 1 avalia "HELLO periódico"; sem log não há como mostrar | D34 |
| Exceção inesperada poderia matar a thread de recepção | "sem derrubar o roteador" | D33 |
| Sincronização e envelhecimento sem log próprio | Critério 2 avalia os dois; precisam ser visíveis | Logs `LSP sincronização` e `LSP envelhecido` (plano §2.3/§4.7) |
| Log de ICMP genérico | "mensagens ICMP geradas" inclui 8 e 0, não só erros | Plano §4.7 |
| Dois enlaces com custo 1 nas topologias | "custos diferentes" pode ser lido como todos distintos | D36 |
| Ordem TTL × rota sem teste | O texto manda checar TTL antes da rota | Teste no plano §4.5 |
| Primeiro HELLO e limites `>= 20`/`>= 90` implícitos | Evitar ambiguidade na implementação | Plano §2.3 |
| Prazo, registro no Moodle, cópia, `.zip` limpo | Regras gerais com nota zero ou não avaliação | Checklist (plano §10) |
| Reinício rápido não recebe sincronização | Comportamento do próprio protocolo; aparece na demo | Explicação + procedimento (plano §10) |
