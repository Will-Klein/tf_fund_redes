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
| 2026-11-19 | Plano aprovado por William. **F0 concluída**: stubs dos 7 módulos com interfaces, configs `local5`/`grupo` (geradas das arestas do plano), README, `.gitignore`, `tests/test_interfaces.py`. Critério da F0 ajustado (iniciar com config real → F1, pois depende do `config.py` do Leonardo) | F1 em paralelo: Leonardo `packets`/`config`, Frederico `dijkstra`, William `log`/Router base; teste de fumaça da VDI |

## Tarefas

| Fase | Tarefa | Dono | Status | Evidência |
|---|---|---|---|---|
| F0 | Estrutura, stubs com interfaces, `.gitignore`, README inicial, `configs/local5` e `configs/grupo` | William | ✅ | `python3 -c "import router, packets, config, dijkstra, forwarding, cli, log"` ok; `python3 router.py` mostra o uso; `python3 -W error::ResourceWarning -m unittest discover tests` → 8 testes OK (Python 3.9.6, 2026-11-19) |
| F0 | Teste de fumaça da VDI (Python ≥ 3.8, UDP entre 2 VMs) | William + 1 | ⬜ | |
| F1 | `packets.py` + testes | Leonardo | ⬜ | |
| F1 | `config.py` + testes | Leonardo | ⬜ | |
| F1 | `dijkstra.py` + testes | Frederico | ⬜ | |
| F1 | `log.py` + `cli.run` mínimo (só `sair`) | William (P2) | ⬜ | |
| F1 | Router base: socket, threads, filtro, despacho, vizinhança + testes | William (P1) | ⬜ | |
| F2 | LSP próprio, recebimento, inundação, sync, aging, recálculo + testes | William (P1) | ⬜ | |
| F2 | `forwarding.py`: DADOS, ICMP, erros, ping + testes | Leonardo | ⬜ | |
| F2 | `cli.py` | William (P2) | ⬜ | |
| F3 | `tests/integration_local.py` passando 3× | William (P2) | ⬜ | |
| F4 | Teste em rede real (ambiente escolhido) | Todos | ⬜ | |
| F4 | Interoperabilidade com outro grupo | Todos | ⬜ | |
| F4 | Capturas `.pcapng` para o relatório | Frederico | ⬜ | |
| F5 | Relatório Q1–Q6 + figura da topologia → PDF | Frederico (+ todos) | ⬜ | |
| F5 | README final | William (P2) | ⬜ | |
| F5 | Roteiro da apresentação (`docs/APRESENTACAO.md`) | Leonardo | ⬜ | |
| F5 | Ensaio da apresentação + simulação de perguntas | Todos (incl. Gustavo) | ⬜ | |
| F5 | Auditoria final e `.zip` | William | ⬜ | |
