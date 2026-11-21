# PROGRESS — Andamento

Legenda: ⬜ não iniciado · 🟨 em andamento · ✅ concluído e testado · ❌ bloqueado.
Regra: só marcar ✅ com teste executado (registrar o comando/resultado na coluna Evidência).

## Registro de sessões

| Data | O que foi feito | Próximo passo |
|---|---|---|
| 2026-11-18 | Análise do enunciado (7 prints), auditoria de segurança (nada suspeito), diagnóstico (repositório vazio), planejamento e documentação em `docs/` | Respostas de William |
| 2026-11-19 | Incorporadas as respostas: G = 6, ambiente VDI (análise em DECISIONS), Leonardo = P3 + apresentação, Frederico = P4, sem cronograma, regra de desempate; revisão de simplicidade (removidos `--quiet` e rastro do Dijkstra) | Conferência literal |
| 2026-11-19 | Cada decisão conferida contra o enunciado: D16→D30 (sem LSP na partida), D31 (sync envia todos os LSPs), D20 sem `ajuda`; Gustavo registrado (R4, apresenta, estuda o código) | Revisão geral |
| 2026-11-19 | G = 6 conferido no Moodle. Revisão geral do plano contra o enunciado: D32–D36, D13/D11 ajustadas, logs de sync/envelhecimento/HELLO, topologias sem empate, checklists operacionais (plano §10) | Aprovação |
| 2026-11-19 | Plano aprovado por William. **F0 concluída**: stubs dos 7 módulos com interfaces, configs `local5`/`grupo` (geradas das arestas do plano), README, `.gitignore`, `tests/test_interfaces.py`. Critério da F0 ajustado (iniciar com config real → F1, pois depende do `config.py` do Leonardo) | Commit inicial e push |
| 2026-11-19 | Branch `p2-log-cli`: `log.py` e `cli.py` implementados e testados (adiantados enquanto Leonardo e Frederico começam a F1); formato dos getters do Router fixado; D37, D38 | Validação |
| 2026-11-19 | Validação de `log.py`/`cli.py` além dos testes unitários: CLI real por pipe e por pseudo-terminal com Ctrl+C (sai limpo, sem traceback), locale C, saída forçada em ASCII (achou travamento com acento → D39), log visível a outro processo em tempo real, sintaxe aceita pelo Python 3.8 | PR #1 |
| 2026-11-19 | PR #1 (log/cli) mergeado. Branch `p1-router`: `router.py` completo (vizinhança, LSP, inundação, sync, envelhecimento, recálculo, rota) + `tests/test_router.py`; contrato do Dijkstra para source fora do grafo | PR #2 |
| 2026-11-19 | PR #2 (router) mergeado. Branch `p2-integracao`: `tests/integration_local.py`, tabelas esperadas completas da `local5` no plano §5, contrato dos textos do forwarding (D40), README com o teste de integração | PR #3 |
| 2026-11-19 | PR #3 (integração) mergeado. Branch `p2-guia-estudo`: `docs/GUIA_ESTUDO.md` parte 1 (router, log, cli): threads e lock, vizinhança, LSP, tabela, robustez, exemplo completo da rede do grupo, 16 perguntas prováveis com resposta, checklist. Nomes e números conferidos no código | Leonardo e Frederico escrevem as partes 2 e 3; todos estudam; rodar a integração com os módulos reais; teste de fumaça da VDI |
| 2026-11-20 | Branch `dijkstra` : `dijkstra.py` implementado (heapq, grafo dirigido, primeiro salto propagado durante o relaxamento) + `tests/test_dijkstra.py` (7 testes: `local5` a partir de R1 e R4, source fora do grafo, grafo só com o source, nó que só aparece como vizinho, aresta só de ida, `local5` sem R2). Parte 3 do `docs/GUIA_ESTUDO.md` escrita | PR de `dijkstra.py`; rodar a integração quando `packets.py`/`config.py`/`forwarding.py` existirem |
| 2026-11-20 | PR #5 (dijkstra) revisado (código morto removido) e mergeado. **Leonardo saiu do grupo → trio.** Redivisão: William fica com `packets.py`/`config.py`, relatório e apresentação; Frederico com `forwarding.py`. Topologia da apresentação vira triângulo de 3 roteadores (D41, D42); configs `grupo`, guia, README e textos dos esboços atualizados | William: `packets.py` + `config.py`; Frederico: `forwarding.py`; atualizar Moodle e avisar o professor |
| 2026-11-21 | PR #6 (redivisão) mergeado. Branch `p3-packets-config`: `packets.py` e `config.py` implementados + `tests/test_packets.py` (21) e `tests/test_config.py` (19). Os 31 testes de router/cli que esperavam o `packets.py` agora rodam (marcações de "pula" removidas). `cli.py` passou a usar `packets.so_digitos` (D43). Guia parte 2 (packets/config) escrita | PR de packets/config; Frederico: `forwarding.py`; depois, relatório |

## Tarefas

| Fase | Tarefa | Dono | Status | Evidência |
|---|---|---|---|---|
| F0 | Estrutura, stubs com interfaces, `.gitignore`, README inicial, `configs/local5` e `configs/grupo` | William | ✅ | `python3 -c "import router, packets, config, dijkstra, forwarding, cli, log"` ok; `python3 router.py` mostra o uso; `python3 -W error::ResourceWarning -m unittest discover tests` → 8 testes OK (Python 3.9.6, 2026-11-19) |
| F0 | Teste de fumaça da VDI (Python ≥ 3.8, UDP entre 2 VMs) | William + 1 | ⬜ | |
| já | Atualizar o grupo no Moodle (trio, sem o Leonardo) e avisar o professor | William | ⬜ | |
| F1 | `packets.py` + testes | William (antes Leonardo) | ✅ | `python3 -W error -m unittest tests.test_packets -v` → 21 testes OK (5 exemplos literais do enunciado ida e volta, lista vazia, tolerâncias D12, cada tipo de malformado, funções de endereço); suíte completa 106/106, 0 pulados (Python 3.9.6, 2026-11-21); sintaxe conferida para Python 3.8 (`ast.parse(feature_version=(3, 8))`) |
| F1 | `config.py` + testes | William (antes Leonardo) | ✅ | `python3 -W error -m unittest tests.test_config -v` → 19 testes OK (arquivo completo, porta padrão 6000, comentários, aviso fora de `10.G.R.1`, as 5 configs `local5`, `grupo` recusada enquanto tiver `IP_Rn`, cada erro com nº da linha). `python3 router.py configs/grupo/r1.conf` → `Erro na configuracao: linha 10: IP do vizinho invalido 'IP_R2' ...` (2026-11-21) |
| F1 | `dijkstra.py` + testes | Frederico | ✅ | `python3 -m unittest tests.test_dijkstra -v` → 7 testes OK (Python 3.9.6, 2026-11-20). Revisão do PR (William): comparação com Bellman-Ford em 20.000 grafos aleatórios sem falhas; suíte completa 66/66 e integração 41/41 com o `dijkstra.py` real (módulos do Leonardo provisórios, fora do repositório). Confere à mão com a tabela esperada da `local5` (plano §5), inclusive o caso sem R2. Falta: rodar com Router/integração reais quando os outros módulos existirem |
| F1 | `log.py` | William (P2) | ✅ | `tests/test_log.py`: 4 testes OK (formato com ms, flush imediato, HELLO só no arquivo, acrescenta ao reiniciar, 4 threads × 200 linhas sem mistura) |
| F1 | Router base: socket, threads, filtro, despacho, vizinhança + testes | William (P1) | ✅ | **2026-11-21, com `packets.py`, `config.py` e `dijkstra.py` reais:** `tests/test_router.py` 30/30 OK; integração `local5` com 5 processos: 31 OK, 0 FALHOU, 1 PULADO (só o bloco do `forwarding.py`). Histórico: `tests/test_router.py`: 3 testes rodavam antes; 27 aguardavam `packets.py`/`dijkstra.py`. Com versões provisórias desses dois (fora do repositório): 59/59 testes OK, e 5 processos reais da topologia `local5` via UDP: tabelas = plano §5; R2 derrubado → R1 inativo em 20 s e rota alternativa via R3 (4/7/12); R2 reiniciado → seq maior aceito, sincronização com as 4 origens; 0 erros. |
| F2 (adiantado) | LSP próprio, recebimento, inundação, sync, aging, recálculo + testes | William (P1) | ✅ | Mesmo arquivo e mesma evidência da linha acima (queda e reinício de R2 conferidos na integração com os módulos reais) |
| F2 | `forwarding.py`: DADOS, ICMP, erros, ping + testes | Frederico (antes Leonardo) | ⬜ | |
| F2 (adiantado) | `cli.py` completo (5 comandos + `sair`) | William (P2) | 🟨 | `tests/test_cli.py`: 17/17 OK com o `packets.py` real (2026-11-21). Validado também com `input()` real: pipe, pseudo-terminal + Ctrl+C, locale C e saída ASCII. Falta: rodar com o Forwarder real (F3) |
| F3 | `tests/integration_local.py` passando 3× | William (P2) | 🟨 | Script pronto (41 verificações: convergência, ping TTL 1-3 R1→R5, ping a host .77, rede inexistente, msg, logs de encaminhamento/ICMP, par desconhecido, malformado, queda de R2 com rotas alternativas, reinício com seq maior e sincronização, `sair`). **2026-11-21, módulos reais (só o forwarding pendente):** 31 OK, 0 FALHOU, 1 PULADO; com o forwarding provisório (fora do repositório) e o resto real: **41 OK, 0 FALHOU** em 2 execuções, convergência em até 7 s. Com packets/config/dijkstra/forwarding provisórios (fora do repositório): **41 OK, 0 FALHOU** em 2 execuções; convergência real ~5 s (logs), reconvergência após queda 18 s. Falta: passar 3× com os módulos reais |
| F4 | Teste em rede real (ambiente escolhido) | Todos | ⬜ | |
| F4 | Interoperabilidade com outro grupo | Todos | ⬜ | |
| F4 | Capturas `.pcapng` para o relatório | William (antes Frederico) | ⬜ | |
| F5 | Relatório Q1–Q6 + figura da topologia → PDF | William (antes Frederico); Frederico revisa a Q1 | ⬜ | |
| F5 | README final | William (P2) | ⬜ | |
| F5 | Roteiro da apresentação (`docs/APRESENTACAO.md`) | William (antes Leonardo) | ⬜ | |
| F5 | Ensaio da apresentação + simulação de perguntas | Todos (incl. Gustavo) | ⬜ | |
| contínuo | Guia de estudo: parte 1 (router, log, cli) | William | ✅ | `docs/GUIA_ESTUDO.md`; nomes de funções, constantes e limites conferidos por busca no código; exemplo bate com `tests/test_router.py` |
| contínuo | Guia de estudo: parte 2 (packets e config) | William | ✅ | `docs/GUIA_ESTUDO.md`, Parte 2A–2E; nomes de funções, mensagens de erro e o exemplo do `IP_R2` conferidos rodando o código |
| contínuo | Guia de estudo: parte 2 (forwarding) | Frederico | ⬜ | |
| contínuo | Pendências da revisão do Dijkstra: teste de empate; "custos não negativos" no guia | Frederico | ⬜ | |
| contínuo | Guia de estudo: parte 3 (dijkstra) | Frederico | ✅ | `docs/GUIA_ESTUDO.md`, Parte 3; nomes de variáveis e o exemplo conferidos contra `dijkstra.py` e contra a `local5` do plano §5 |
| F5 | Auditoria final e `.zip` | William | ⬜ | |
