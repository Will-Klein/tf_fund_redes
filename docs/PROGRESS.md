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
| 2026-11-19 | PR #2 (router) mergeado. Branch `p2-integracao`: `tests/integration_local.py`, tabelas esperadas completas da `local5` no plano §5, contrato dos textos do forwarding (D40), README com o teste de integração | Rodar a integração com os módulos reais dos colegas; teste de fumaça da VDI |

## Tarefas

| Fase | Tarefa | Dono | Status | Evidência |
|---|---|---|---|---|
| F0 | Estrutura, stubs com interfaces, `.gitignore`, README inicial, `configs/local5` e `configs/grupo` | William | ✅ | `python3 -c "import router, packets, config, dijkstra, forwarding, cli, log"` ok; `python3 router.py` mostra o uso; `python3 -W error::ResourceWarning -m unittest discover tests` → 8 testes OK (Python 3.9.6, 2026-11-19) |
| F0 | Teste de fumaça da VDI (Python ≥ 3.8, UDP entre 2 VMs) | William + 1 | ⬜ | |
| F1 | `packets.py` + testes | Leonardo | ⬜ | |
| F1 | `config.py` + testes | Leonardo | ⬜ | |
| F1 | `dijkstra.py` + testes | Frederico | ⬜ | |
| F1 | `log.py` | William (P2) | ✅ | `tests/test_log.py`: 4 testes OK (formato com ms, flush imediato, HELLO só no arquivo, acrescenta ao reiniciar, 4 threads × 200 linhas sem mistura) |
| F1 | Router base: socket, threads, filtro, despacho, vizinhança + testes | William (P1) | 🟨 | `tests/test_router.py`: 3 testes rodam já; 27 aguardam `packets.py`/`dijkstra.py` (rodam sozinhos depois). Com versões provisórias desses dois (fora do repositório): 59/59 testes OK, e 5 processos reais da topologia `local5` via UDP: tabelas = plano §5; R2 derrubado → R1 inativo em 20 s e rota alternativa via R3 (4/7/12); R2 reiniciado → seq maior aceito, sincronização com as 4 origens; 0 erros. Falta: rodar com os módulos reais |
| F2 (adiantado) | LSP próprio, recebimento, inundação, sync, aging, recálculo + testes | William (P1) | 🟨 | Mesmo arquivo e mesma evidência da linha acima |
| F2 | `forwarding.py`: DADOS, ICMP, erros, ping + testes | Leonardo | ⬜ | |
| F2 (adiantado) | `cli.py` completo (5 comandos + `sair`) | William (P2) | 🟨 | `tests/test_cli.py`: 13 testes OK + 4 de `msg`/`ping` pulados até o `packets.py` existir (rodam sozinhos depois); os 17 passaram com uma validação provisória fora do repositório. Validado também com `input()` real: pipe, pseudo-terminal + Ctrl+C, locale C e saída ASCII. Falta: rodar com o `packets.py` real e com Router/Forwarder reais (F3) |
| F3 | `tests/integration_local.py` passando 3× | William (P2) | 🟨 | Script pronto (41 verificações: convergência, ping TTL 1-3 R1→R5, ping a host .77, rede inexistente, msg, logs de encaminhamento/ICMP, par desconhecido, malformado, queda de R2 com rotas alternativas, reinício com seq maior e sincronização, `sair`). Com os módulos atuais para no início e mostra o motivo (`config.py` pendente). Com packets/config/dijkstra/forwarding provisórios (fora do repositório): **41 OK, 0 FALHOU** em 2 execuções; convergência real ~5 s (logs), reconvergência após queda 18 s. Falta: passar 3× com os módulos reais |
| F4 | Teste em rede real (ambiente escolhido) | Todos | ⬜ | |
| F4 | Interoperabilidade com outro grupo | Todos | ⬜ | |
| F4 | Capturas `.pcapng` para o relatório | Frederico | ⬜ | |
| F5 | Relatório Q1–Q6 + figura da topologia → PDF | Frederico (+ todos) | ⬜ | |
| F5 | README final | William (P2) | ⬜ | |
| F5 | Roteiro da apresentação (`docs/APRESENTACAO.md`) | Leonardo | ⬜ | |
| F5 | Ensaio da apresentação + simulação de perguntas | Todos (incl. Gustavo) | ⬜ | |
| F5 | Auditoria final e `.zip` | William | ⬜ | |
