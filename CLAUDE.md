# Instruções para sessões de IA neste repositório

Antes de qualquer trabalho, leia nesta ordem:
1. `docs/PROJECT_CONTEXT.md` (contexto, requisitos, divisão, riscos)
2. `docs/PROGRESS.md` (onde paramos)
3. `docs/DECISIONS.md` e `docs/IMPLEMENTATION_PLAN.md` conforme a tarefa
4. `docs/ENUNCIADO.md` é a fonte de verdade dos requisitos
5. `docs/GUIA_ESTUDO.md`: explicação do código para o grupo; ao mudar um módulo, atualize a parte dele

Regras:
- Formatos de pacote e regras de processamento seguem o enunciado **literalmente** (interoperabilidade).
- Python 3.8+ só com biblioteca padrão; Dijkstra implementado à mão (proibido networkx/scipy).
- Código simples e comentado em português: todos os integrantes precisam conseguir explicá-lo
  (regra do professor: código não explicável = nota zero).
- Não marcar nada como concluído sem teste executado; atualizar `docs/PROGRESS.md` ao terminar uma tarefa.
- Decisão nova ou mudança de interpretação → registrar em `docs/DECISIONS.md`.
- Texto que vai para a tela ou para o log: ASCII, sem acentos (D39). Comentários podem ter acento.
- Regra de desempate (William): onde o enunciado não define, estudar antes e escolher o que cumpre o
  texto literalmente **e** é o mais simples de implementar e explicar. Sem complexidade que não dê nota.
- Dados fixos: Grupo G = 6 (`10.6.R.1`), ambiente VDI, **trio** desde 2026-11-20 (Leonardo saiu): R1 William, R2 Frederico, R3 Gustavo (não escreve código neste trabalho, mas apresenta); apresentação com 3 roteadores (D41).
