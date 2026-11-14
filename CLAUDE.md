# CLAUDE.md

Guia para o Claude Code ao trabalhar neste repositório. Especificação completa em [PRD.md](PRD.md) — leia-o antes de implementar qualquer funcionalidade nova.

## O que é este projeto

Sistema de adequação de escala de funcionários à nova lei da escala 5x2 (EC 141/2026). É uma ferramenta interna de um escritório de contabilidade, usada para gerar e validar escalas de trabalho dos seus clientes (empresas), considerando dias de descanso semanal, revezamento dominical (regras diferentes por sexo e setor) e carga horária semanal — que pode variar por empresa-cliente (algumas aderem a jornadas inferiores a 42h).

## Arquitetura (decidida, não renegociar sem o usuário)

- **100% client-side**, hospedado como site estático no **GitHub Pages**. Não há backend/servidor.
- Lógica de negócio em **Python**, executada no navegador via **Pyodide**.
- Interface em **HTML/CSS/JS puro** (sem framework de front-end).
- Persistência via **SQLite dentro do navegador** (Pyodide + `sqlite3`), com o arquivo do banco mantido em **IndexedDB**. Não existe banco central — cada navegador/dispositivo tem seus próprios dados. Backup/portabilidade é feito via exportação/importação manual de arquivo.
- Sem login/autenticação.

Qualquer sugestão de mudança nessa arquitetura (ex. adicionar backend, trocar de linguagem) deve ser validada com o usuário antes de implementar — não decidir isso unilateralmente.

A exportação de PDF usa `jsPDF` + `jspdf-autotable` (carregadas via CDN no `index.html`), não Python/Pyodide — gerar PDF com `reportlab` dentro do Pyodide seria mais pesado e não foi necessário.

## Regras de negócio já implementadas (não regredir sem o usuário pedir)

Resumo rápido do que já está em produção no código — a especificação completa de cada uma está no PRD.md, mas isto serve para não reintroduzir um comportamento já corrigido:

- **Carga horária contratada** pode ser igual ou inferior ao limite da fase da lei (42h/40h); **não há limite fixo de horas diárias** (ex.: nada de assumir 8h/dia).
- **Jornada diária do turno = carga horária semanal ÷ 5**, sempre, para todos os turnos da empresa — não existe mais horário de início/fim nem intervalo configurável por turno; o único dado do turno é o nome e se é revezamento. Não reintroduzir campos de horário sem o usuário pedir.
- **Turno fixo por funcionário**: cada funcionário é alocado a um único turno (não alterna turnos dia a dia).
- **Checkboxes de turno de cada funcionário vêm marcadas por padrão** (todos os turnos cadastrados) — ao adicionar um funcionário ou um turno novo, o JS já popula/atualiza `turnosPermitidos` com todos os ids existentes em vez de deixar vazio; o usuário só desmarca exceções. Não confundir com o fallback do Python (`_turnos_aptos`: lista vazia = apto a tudo) — esse fallback continua existindo para dados salvos antes dessa mudança, mas o front-end não depende mais dele para o caso normal.
- **Dias de funcionamento padrão: Segunda a Sábado marcados, Domingo desmarcado** (checkboxes em `index.html`).
- **No máximo 2 folgas por semana por funcionário** — os dias em que a empresa fecha já contam dentro dessas 2, nunca se soma folga extra além disso (só mais que 2 quando a carga horária realmente obriga). Não reintroduzir uma lógica que dê folga "de bônus" além das 2 (ex.: sábado como folga aditiva já foi um bug corrigido — ver histórico).
- **Folgas em dias fixos da semana** sempre que possível; os dias de **domingo** e **sábado** (quando a empresa funciona neles) são exceção proposital — eles giram em rodízio, não ficam fixos.
- **Domingo e sábado são, por padrão, as 2 folgas de todo mundo** (domingo por preferência da EC 141/2026; sábado por regra de distribuição justa) — só o mínimo necessário por turno é escalado para trabalhar nesses dias, em rodízio; quem é escalado troca aquela folga por um dia de semana, sem ultrapassar as 2 folgas totais. Não é "trabalha por padrão, descansa quando devido", é o contrário. No domingo, o limite legal (mulheres: escala quinzenal — **no máx. 1 domingo seguido** trabalhado, `PERIODO_DOMINGO_MULHER_DIAS = 7` em `regras.py`, art. 386 CLT, vale mesmo no comércio; demais: 7 semanas geral ou 3 semanas comércio) funciona como teto de quantas vezes seguidas a pessoa pode ser escalada para trabalhar, não como gatilho para forçar folga. Não confundir com "até 15 dias sem folga" — o teto de 7 dias é proposital, porque a lei exige alternância (trabalhou um domingo, o seguinte é de folga), não uma janela de 15 dias. Sábado usa o mesmo mecanismo mas sem teto legal (`_selecionar_trabalhadores_domingo` e `_selecionar_trabalhadores_sabado` em `gerador_escala.py`).
- **A escala sempre mostra os 7 dias da semana** (tela/impressão/PDF, via `diasExibidosNaEscala()`), mesmo nos dias em que a empresa não funciona (mostrados como "Folga" fixa) — não voltar a filtrar só pelos dias de funcionamento.
- **Escala sempre gerada para 4 semanas** (constante `SEMANAS_POR_ESCALA` em `gerador_escala.py`).
- **"Gerar escala" salva automaticamente** os dados do formulário antes de gerar — não depende de clicar em "Salvar" antes.
- **Nome do funcionário em branco** vira `F1`, `F2`, `F3`... pela ordem de cadastro (`nomeExibicaoFuncionario`, no front-end, antes de persistir). **Nome do turno em branco** vira `Turno 1`, `Turno 2`... do mesmo jeito (`nomeExibicaoTurno`).
- **Botão "Limpar formulário"** reinicia nome/setor/fase/carga/dias/turnos da seção 1 inteira (com confirmação) — não é só para turnos.
- Todas as horas mostradas ao usuário (tela e avisos) usam o formato `Xh` / `XhYYmin` (`formatarHorasMinutos` no JS, `formatar_horas` no Python), nunca decimal.
- **Violações são destacadas diretamente na grade da escala** (fundo vermelho, texto branco — classe `.celula-violacao`), além de listadas em "Conformidade". `aplicarDestaquesViolacoes()` usa o campo `dia` que `validador.py` inclui em cada violação (e `turno_id` nas de revezamento) para achar a célula certa via `data-semana`/`data-dia`/`data-funcionario-id` no DOM.

## Estrutura de arquivos

```
index.html              # interface principal
css/style.css           # estilos gerais
css/print.css           # estilos de impressão/PDF
js/app.js               # bootstrap do Pyodide, IndexedDB e bindings de UI
python/regras.py        # parâmetros legais (5x2, domingo, carga horária)
python/gerador_escala.py  # algoritmo heurístico de geração de escala
python/validador.py     # validação (tanto a escala gerada quanto a editada à mão)
python/persistencia.py  # schema SQLite e leitura/escrita
python/ponte.py         # funções chamadas pelo app.js (recebem/retornam JSON)
.claude/launch.json     # servidor estático local (python -m http.server), só para dev
PRD.md
CLAUDE.md
```

## Convenções

- Textos de interface e mensagens de validação: **português (pt-BR)**, incluindo a referência à base legal (ex. "Art. 386 da CLT") quando apontar uma violação.
- Nomes de módulos/funções/variáveis de domínio (escala, funcionário, turno, revezamento) seguem em português, para casar com os termos já usados no PRD e na legislação — não traduzir para inglês.
- Nenhum parâmetro legal (datas de vigência, limites de hora, periodicidade de domingo) deve ser fixo ("hardcoded") no meio da lógica — tudo deve vir de configuração editável pelo usuário, porque a regulamentação pode mudar.
- Sem comentários explicando o óbvio; comentar apenas regras legais não óbvias (ex. por que a regra de domingo das mulheres é diferente).
- Não introduzir backend, banco de dados externo ou dependências de build (bundlers, frameworks) sem alinhar antes — o projeto é intencionalmente simples e estático.

## Como testar

Abrir `index.html` direto do disco (`file://`) **não funciona**: o `fetch()` que carrega os módulos Python é bloqueado por CORS nesse esquema. É preciso servir a pasta por HTTP. Já existe um `.claude/launch.json` configurado para isso — use o Claude Code para iniciá-lo (`preview_start` com o nome `escala-5x2-static`) ou rode manualmente:

```bash
python .claude/dev_server.py 8787
```

É um `http.server` com `Cache-Control: no-store` forçado em tudo (`.claude/dev_server.py`) — não usar `python -m http.server` puro aqui, porque o navegador (e principalmente este servidor de preview do Claude Code) chegou a cachear `index.html`/`app.js` de forma persistente mesmo depois de um hard refresh, escondendo correções já aplicadas no código.

e abra `http://localhost:8787`. Teste sempre o fluxo completo: cadastro da empresa/turnos → cadastro de funcionários → gerar escala → ajuste manual de uma célula → conferir se a validação recalculou → exportações (CSV, PDF, backup) → recarregar a página e confirmar que os dados persistiram (IndexedDB).

**Pegadinha do Pyodide:** o módulo `sqlite3` não vem por padrão no runtime — é preciso `await pyodide.loadPackage("sqlite3")` antes de importar `persistencia.py` (já feito em `js/app.js`). Se note um `ModuleNotFoundError: sqlite3`, é esse carregamento que está faltando.

**Pegadinha de cache:** `index.html` referencia `css/style.css`, `css/print.css` e `js/app.js` com `?v=N` para evitar que o navegador sirva uma versão em cache depois de uma mudança (GitHub Pages também cacheia agressivamente). **Sempre que editar esses três arquivos, incremente o `N` em `index.html`.** Os módulos Python em `python/*.py` já são buscados com `{ cache: "no-store" }` em `js/app.js`, então não têm esse problema. Isso resolve o cache de `app.js`/CSS, mas **o próprio `index.html` também pode ficar em cache** (observado no servidor de dev local) — se uma mudança não aparecer mesmo depois de editar o arquivo, faça um hard refresh (Ctrl+Shift+R) ou abra em uma aba nova antes de concluir que o código está errado.

**Pegadinha de "travamento" silencioso:** chamadas ao `ponte` (via `pyodide`) que lançam uma exceção Python dentro de um `async` handler viram uma *unhandled promise rejection* — o clique no botão simplesmente não faz nada visível, parecendo travado, sem nenhuma mensagem na tela. Por isso todo handler que chama `ponte.*` em `js/app.js` está envolto em `try/catch` que mostra o erro em `.mensagem.erro`. Ao adicionar um novo botão/handler que chame `ponte`, sempre envolver em `try/catch` — nunca deixar a chamada "nua". `persistencia.salvar_funcionarios` também usa `INSERT OR REPLACE` (não `INSERT` puro) para nunca travar com `UNIQUE constraint failed` se a lista vinda do front-end tiver algum id repetido.

**Pegadinha de ponto flutuante:** divisões como `carga_horaria / horas_turno` (ex.: `42 / 8.4`) podem dar `4.999999...` em vez de `5.0` por imprecisão de float, e um `//`/`int()` direto arredondaria para baixo errado. Em `gerador_escala.py` isso é corrigido somando um epsilon (`+ 1e-9`) antes de truncar — mantenha esse cuidado em qualquer cálculo novo que divida horas.
