# PRD — Sistema de Adequação de Escala de Funcionários (Escala 5x2)

## 1. Contexto e motivação

A Emenda Constitucional nº 141/2026 (originada da PEC 221/2019) extingue a escala 6x1 e institui a escala **5x2** (2 dias de descanso semanal remunerado por semana), em duas fases:

| Fase | Jornada máxima semanal | Vigência estimada |
|---|---|---|
| 1 | 42 horas | a partir de ~16/12/2026 (60 dias após a promulgação) |
| 2 | 40 horas | a partir de ~16/12/2027 (cerca de 1 ano depois) |

Sem redução salarial em nenhuma das fases.

Regras de descanso dominical que coexistem com a emenda:

- **Regra geral:** 1 domingo de folga a cada 7 semanas (Lei 605/1949).
- **Mulheres no setor geral:** escala quinzenal — se trabalhar um domingo, o domingo seguinte deve ser de folga (art. 386 da CLT).
- **Comércio (homens e mulheres):** no máximo 2 domingos trabalhados seguidos — pode folgar 1 domingo e voltar a trabalhar, ou folgar 2 domingos seguidos (Lei 10.101/2000). É uma exceção expressa à escala quinzenal da mulher: no comércio, ela também pode trabalhar 2 domingos seguidos, não só 1 — essa exceção não se aplica ao setor geral.
- A EC 141/2026 recomenda que, dos 2 dias de descanso semanal, **um seja preferencialmente o domingo**.

A aplicação deve ajudar empresas a montar escalas de trabalho que já nasçam aderentes a essas regras, evitando montagens manuais sujeitas a erro.

> As datas de vigência e o texto final da emenda devem ser confirmados no Diário Oficial antes de travar regras "hardcoded"; o sistema deve tratá-las como **parâmetros configuráveis**, não como constantes fixas no código.

## 2. Objetivo do produto

Ferramenta web, de uso interno e poucos acessos, que:

1. Recebe os dados da empresa e dos funcionários.
2. **Gera automaticamente** uma sugestão de escala semanal aderente à lei.
3. Permite **ajuste manual** da escala gerada, com **validação em tempo real** apontando violações.
4. Exporta/imprime o resultado final.

## 3. Decisões de arquitetura (definidas com o usuário)

| Decisão | Escolha |
|---|---|
| Hospedagem | 100% estática, publicada no **GitHub Pages** (sem servidor/backend) |
| Linguagem de lógica | **Python**, executado no navegador via **Pyodide** (WebAssembly) |
| Interface | HTML/CSS/JS, consumindo as funções Python carregadas pelo Pyodide |
| Persistência | **SQLite local** rodando no navegador (via `sqlite3` do Pyodide), com o arquivo de banco mantido em **IndexedDB** do navegador |
| Backup/portabilidade | Botões de **exportar/importar** um arquivo `backup-escala.json` (empresa, funcionários e escala), já que não há servidor central guardando os dados. O banco SQLite fica no IndexedDB do navegador e não é exportado diretamente |
| Acesso | Sem login — aplicação de uso livre, pensada para uma única empresa por "instalação" (por navegador/dispositivo) |
| Função principal | Gerar escala sugerida automaticamente **e** permitir validação/ajuste manual |
| Formatos de saída | Visualização em tela + impressão (PDF do navegador) + exportação Excel/CSV + PDF formatado pela aplicação |
| Abrangência da validação | Dias de descanso (5x2), revezamento dominical por sexo/setor, **e** carga horária diária/semanal conforme a carga contratada pela empresa (até o limite da fase da lei: 42h ou 40h) |

**Observação técnica importante:** como a hospedagem é 100% estática (GitHub Pages), não existe servidor para manter um banco de dados "vivo" entre acessos de diferentes dispositivos. A persistência via SQLite/IndexedDB funciona **por navegador/dispositivo** — ou seja, os dados salvos no PC do RH não aparecem automaticamente no notebook de outra pessoa, a menos que o arquivo `.db` seja exportado e importado manualmente. Isso é aceitável dado o cenário de poucos acessos, mas deve estar claro para o usuário final da aplicação (um aviso na própria tela).

## 4. Personas

- **RH / Gestor de escala**: preenche os dados da empresa e funcionários, gera a escala, ajusta manualmente quando necessário, exporta o resultado.

Não há perfis de administrador, aprovador ou funcionário final nesta versão (sem login, uso único por sessão/dispositivo).

## 5. Dados de entrada (telas de cadastro)

### 5.1 Dados da empresa
- Nome da empresa (texto livre, opcional — só para exibir no relatório).
- **Setor**: `Geral` ou `Comércio` (define a regra de periodicidade dominical aplicada aos homens/demais funcionários).
- **Fase da lei vigente**: `42 horas` ou `40 horas` (seleção manual, com data de referência sugerida automaticamente com base na data do sistema, mas editável). *Pendência: hoje existe apenas a seleção, sem a data de referência.* Define o **limite máximo** legal permitido para a carga horária semanal.
- **Carga horária semanal contratada**: campo numérico de preenchimento livre (ex.: 44h, 40h, 36h, 30h...), pensado para empresas-cliente da contabilidade que adotam jornada **igual ou inferior** ao limite legal da fase vigente. A aplicação valida que esse valor não pode ser **maior** que o limite da fase selecionada, mas aceita qualquer valor igual ou menor — cada empresa cadastrada pode ter a sua própria carga horária.
- **Dias da semana em que a empresa funciona**: checkboxes de Segunda a Domingo (múltipla escolha). Padrão: **Segunda a Sábado marcados**, Domingo desmarcado — o usuário ajusta conforme o caso.
- **Jornada diária (todos os turnos)**: calculada e exibida automaticamente como **carga horária semanal contratada ÷ 5** (ex.: 42h ÷ 5 = 8h24min/dia), sempre em horas e minutos, nunca em decimal. É o mesmo valor para todos os turnos da empresa.
- **Quantidade de turnos**: o usuário adiciona quantos turnos quiser (ex.: "Manhã", "Tarde"). Para cada turno só é preciso informar:
  - Nome — se deixado em branco, a aplicação adota automaticamente **"Turno 1", "Turno 2", "Turno 3"...**, conforme a ordem de cadastro.
  - Se o turno opera em **regime de revezamento** (exige no mínimo 2 funcionários simultâneos — ver 5.3).

  Não é preciso informar horário de início/fim nem intervalo: a duração do turno é sempre a jornada diária acima, derivada da carga horária contratada. **Não há limite fixo de horas diárias (ex.: 8h/dia) nesta fase da lei** — o limite diário é o que resulta da divisão da carga semanal por 5, consistente com a EC 141/2026 permitir, durante a fase de 42h, jornada diária ampliada por convenção/acordo coletivo, desde que mantidos os 2 dias de descanso.
- Botão **"Limpar formulário"**: reinicia de uma vez nome, setor, fase, carga horária, dias de funcionamento e todos os turnos cadastrados nesta seção (com confirmação antes de apagar, para evitar perda acidental).

### 5.2 Dados de funcionários
- Quantidade total de funcionários: não é campo de entrada; é calculada a partir da lista cadastrada.
- Para cada funcionário (formulário repetível; *importação via CSV/Excel ainda não implementada*):
  - Nome — **se deixado em branco, a aplicação adota automaticamente a sequência F1, F2, F3...**, conforme a ordem de cadastro.
  - Sexo (`Masculino` / `Feminino`) — usado para aplicar a regra de domingo correta (art. 386 CLT para mulheres).
  - Turno(s) em que pode atuar — **por padrão, todos os turnos cadastrados já vêm marcados** para cada funcionário (e um novo turno marca automaticamente para todo mundo); o usuário só desmarca quando um funcionário específico não pode atuar em determinado turno.
  - Carga horária semanal contratada individual (se diferente do padrão da empresa) — *pendência: hoje todos usam a carga horária da empresa*.
- Totais calculados automaticamente e exibidos: nº de homens e nº de mulheres (implementado). *Pendência: nº de funcionários por turno ainda não é exibido.*

### 5.3 Revezamento de turnos
- Marcar quais turnos operam em **regime de revezamento** (ex.: turno noturno 24h).
- Para turnos marcados como revezamento, a aplicação **exige no mínimo 2 funcionários alocados** àquele turno simultaneamente. A aplicação não bloqueia o campo: se um turno de revezamento ficar com menos de 2 pessoas num dia, esse dia aparece como alerta na grade e na lista de Conformidade.
- Turno sem revezamento: mínimo de **1 funcionário** em cada dia de funcionamento.

## 6. Geração da escala (motor de regras)

A escala é sempre gerada para um horizonte fixo de **4 semanas**. Ao clicar em **"Gerar escala"**, a aplicação salva automaticamente os dados preenchidos no formulário (empresa, turnos e funcionários) antes de gerar — **não é preciso clicar em "Salvar" manualmente antes**.

Algoritmo heurístico (não é um otimizador exato/CSP completo nesta versão) que, a partir dos dados de entrada, tenta:

0. Atribuir cada funcionário a um **turno inicial** (entre os que ele é apto a atuar, balanceando a quantidade de pessoas por turno). Esse turno é a prioridade mais baixa: em cada dia, se um turno ficaria abaixo do mínimo, um funcionário apto a ele (mesmo que atribuído a outro turno) pode cobrir a falta naquele dia. Calcular, a partir da carga horária contratada dividida por 5 (a jornada diária, igual para todos os turnos — ver 5.1), **quantos dias por semana ele pode efetivamente trabalhar** — isso evita, por construção, o estouro de carga horária que uma distribuição "preencha todos os dias úteis" causaria.
1. **No máximo 2 dias de descanso por semana** para cada funcionário (escala 5x2) — os dias em que a empresa fecha já contam dentro dessas 2 folgas, não se soma folga extra além disso (ex.: empresa fechada sábado e domingo = exatamente essas 2 folgas, sem folga adicional). A única exceção é quando a carga horária contratada, dividida pela jornada diária do turno, resulta em menos dias de trabalho do que isso permitiria — nesse caso há mais de 2 folgas, inevitavelmente.
1b. **Folgas em dias fixos da semana, sempre que possível**: cada funcionário tende a folgar nos mesmos dias toda semana (previsibilidade), exceto nos dias sujeitos a rodízio obrigatório — domingo e sábado (pontos 2 e 2b) — que variam de propósito.
2. **Domingo e sábado (quando a empresa funciona neles) são, por padrão, os 2 dias de folga de todo mundo** — não ficam "de fora" das 2 folgas, são a forma mais comum de cumpri-las. Só o mínimo necessário para cobrir o turno é escalado para trabalhar nesses dias, girando entre os colegas de turno semana a semana; quem é escalado troca a folga de sábado ou domingo por um dia de semana naquela semana (sem ultrapassar as 2 folgas totais). No domingo, a rotação respeita o limite legal de cada um sem ultrapassá-lo:
   - Mulheres, setor geral: **escala quinzenal** — no máximo **1 domingo trabalhado seguido**; o domingo seguinte ao que ela trabalhou tem que ser de folga (art. 386 da CLT).
   - Homens / demais, setor geral: podem ser escalados por até **7 semanas seguidas** antes de ter que folgar no domingo (Lei 605/1949).
   - Comércio, homens e mulheres: podem ser escalados por até **2 domingos seguidos** antes de ter que folgar no domingo (Lei 10.101/2000) — é uma exceção à escala quinzenal da mulher, que no comércio passa a poder trabalhar 2 domingos seguidos em vez de apenas 1; essa exceção não se aplica ao setor geral.
   - Quando não há, entre os colegas de turno, gente suficiente dentro do próprio limite legal para cobrir o mínimo do domingo, a aplicação aloca quem tiver disponível mesmo assim e **avisa explicitamente** que o limite foi ultrapassado por falta de funcionários.
2b. **Revezamento do sábado**: mesmo princípio do domingo, mas sem base legal específica — é uma regra de distribuição justa definida pelo usuário, sem teto de semanas seguidas.
3. Em turnos marcados como revezamento, manter **sempre ao menos 2 funcionários** por turno/dia; em turnos sem revezamento, **ao menos 1** por dia de funcionamento. Ter ao menos o mínimo em cada turno é prioridade acima das folgas (item 0 e item 1 — a cobertura tem prioridade sobre a folga, e o turno fixo é a prioridade mais baixa).
4. Distribuir a carga horária semanal de cada funcionário sem exceder a **carga horária semanal contratada pela empresa** (que pode ser igual ou inferior ao limite legal da fase vigente — 42h ou 40h).
5. Quando não for possível atender a todas as regras com os dados informados (ex.: funcionários insuficientes para cobrir o mínimo de revezamento com a carga horária configurada), a aplicação **não força uma escala inválida**: ela gera a melhor aproximação possível e **explica a causa raiz** em uma seção de observações (ex.: "o turno de 8h24min/dia permite no máximo 5 dias de trabalho..." ou "os funcionários alocados somam menos dias-pessoa do que o necessário para o mínimo de revezamento"), além de sinalizar as violações pontuais resultantes para decisão humana.
6. **A escala sempre mostra os 7 dias da semana** (tela, impressão e PDF), mesmo nos dias em que a empresa não funciona — esses dias aparecem como "Folga" fixa, para deixar explícito que ali não há trabalho.
7. **A escala de 4 semanas é feita para se repetir**: a empresa reaplica o mesmo ciclo mês a mês, então a transição do fim da última semana para a semana 1 do próximo ciclo também precisa respeitar o limite de domingos seguidos — não só as 4 semanas vistas isoladamente. A aplicação corrige isso automaticamente, trocando a folga inteira de quem trabalharia além do limite na virada por um colega do mesmo grupo de turnos com a mesma carga horária; quando o quadro de funcionários é pequeno demais para isso ser possível (ex.: só 3 pessoas num turno de revezamento mínimo de 2, no comércio), a aplicação avisa que não há como evitar e a violação residual aparece destacada na escala, como qualquer outra.

## 7. Validação (modo manual/ajuste)

Após a geração automática, o usuário pode arrastar/editar manualmente a alocação de qualquer funcionário em qualquer dia/turno. A cada alteração, a aplicação revalida em tempo real e exibe, por funcionário:

- ✅ Cumprindo: 2 dias de descanso na semana, limite de horas semanais, periodicidade de domingo.
- ⚠️ Alerta: ex. turno de revezamento com menos de 2 pessoas num dia; turno comum sem nenhuma pessoa num dia de funcionamento.
- ❌ Violação: ex. funcionária do setor geral que trabalhou um domingo e também trabalhou no domingo seguinte; no comércio, mais de 2 domingos seguidos trabalhados; funcionário excedendo a carga horária semanal contratada pela empresa; menos de 2 dias de descanso.

Cada violação exibe um texto curto explicando a regra infringida e sua base legal (ex. "Art. 386 da CLT — mulher sem domingo de descanso há mais de 7 dias, setor geral"). Além da lista, **a própria célula (ou cabeçalho do dia) onde a violação ocorre é destacada em vermelho com texto branco diretamente na grade da escala**, para o usuário identificar o problema no lugar sem precisar cruzar com a lista.

## 8. Relatórios e exportação

- **Visualização em tela**: grade semanal (funcionário × dia × turno), com código de cores para descanso/trabalho e indicadores de conformidade.
- **Impressão/PDF do navegador**: layout otimizado para impressão (CSS de impressão dedicado).
- **Exportação CSV**: a mesma grade da tela/PDF (funcionário × dia, todas as 4 semanas, todos os 7 dias, incluindo "Folga"), em um único arquivo `.csv` com separador `;`, em formato de lista (uma linha por semana × funcionário, com as colunas Semana, Funcionário e os 7 dias) — abre direto no Excel/planilha, sem precisar de biblioteca extra para gerar `.xlsx`. O arquivo é gravado com BOM UTF-8, para o Excel reconhecer os acentos.
- **PDF formatado pela aplicação**: gerado no navegador via biblioteca JavaScript (`jsPDF` + `jspdf-autotable`, carregadas por CDN) — mais leve que gerar PDF em Python/Pyodide —, com cabeçalho da empresa, data de geração, uma tabela por semana, uma seção **Conformidade** e a **legenda das regras de domingo** ao final (regra geral, mulheres no setor geral, comércio e a recomendação da EC 141/2026). Sem rodapé.

Na grade de cada semana, as células onde há violação são marcadas em vermelho com texto branco, do mesmo jeito que na tela (a célula do funcionário no dia, o nome do funcionário ou o cabeçalho do dia com as células do turno naquele dia).

A seção **Conformidade** do PDF lista cada violação (funcionário, texto e base legal) com as mesmas cores da tela — vermelho para violação e laranja para alerta. Quando não há violação, aparece a mensagem de conformidade em verde.

## 9. Persistência de dados

- Cadastro de empresa, funcionários e última escala gerada/ajustada ficam salvos em SQLite dentro do navegador (IndexedDB), recuperados automaticamente na próxima abertura da aplicação **no mesmo navegador/dispositivo**.
- Botão **"Exportar backup"**: baixa um arquivo com todos os dados (empresa, funcionários, escala).
- Botão **"Importar backup"**: restaura os dados a partir de um arquivo exportado anteriormente (permite mover os dados entre dispositivos ou recuperar após limpar o navegador).

## 10. Fora de escopo (nesta versão)

- Login/autenticação e multiempresa/multiusuário.
- Validação do intervalo intrajornada mínimo por lei (ex.: 1h para jornadas acima de 6h). A aplicação não pede horário de início/fim nem intervalo: a jornada diária é sempre a carga horária semanal ÷ 5. Banco de horas/horas extras também ficam de fora.
- Feriados municipais/estaduais e calendário de férias.
- Otimização matemática exata da escala (algoritmo é heurístico, não garante a solução ótima global).
- Hospedagem com backend/servidor próprio ou banco de dados centralizado na nuvem.

## 11. Estrutura de arquivos proposta (alto nível)

```
/ (raiz do repositório GitHub Pages)
├── index.html              # interface principal (cadastro + escala + relatórios)
├── css/
│   ├── style.css
│   └── print.css            # estilos específicos para impressão/PDF
├── js/
│   └── app.js               # inicialização do Pyodide, IndexedDB, bindings de UI
├── python/
│   ├── regras.py            # parâmetros legais (5x2, domingo, carga horária)
│   ├── gerador_escala.py    # algoritmo heurístico de geração
│   ├── validador.py         # validação (geração e edição manual)
│   ├── persistencia.py      # schema e leitura/escrita no SQLite
│   └── ponte.py             # funções chamadas pelo app.js (entrada/saída em JSON)
├── .claude/launch.json       # configuração do servidor de preview
├── .claude/dev_server.py     # servidor estático local (sem cache) só para desenvolvimento/teste
├── PRD.md                   # este documento
└── CLAUDE.md
```

> O módulo `python/ponte.py` não estava no desenho original da seção 11, mas foi necessário como camada fina de tradução JSON entre o JavaScript e os módulos de regra — mantém `regras.py`, `gerador_escala.py` e `validador.py` livres de qualquer detalhe de integração com o navegador.

## 12. Riscos e premissas

- **Premissa**: o texto final da EC 141/2026 e os prazos de transição podem ser ajustados por regulamentação posterior; os parâmetros de data/jornada devem ficar editáveis na tela de configuração, não fixos no código.
- **Risco**: a combinação "site estático + persistência local por navegador" significa que, se o usuário limpar os dados do navegador sem ter exportado backup, os dados cadastrados se perdem. Mitigado pelo botão de exportação, mas depende do usuário lembrar de usá-lo.
- **Risco**: o repositório é público (exigência do GitHub Pages gratuito), então o código e as regras de negócio ficam visíveis a qualquer pessoa. Dados de funcionários nunca devem ser commitados no repositório.
- **Risco jurídico**: a aplicação é ferramenta de apoio e não substitui orientação de advogado trabalhista. As interpretações das regras (ex.: teto de domingos seguidos no comércio, exceção à escala quinzenal da mulher) devem ser validadas juridicamente antes de uso com clientes.
- **Risco**: Pyodide tem um tempo de carregamento inicial (alguns segundos, baixando o runtime Python via WebAssembly) — aceitável para uma ferramenta de uso esporádico, mas deve ser comunicado ao usuário (tela de carregamento).

## 13. Status e próximos passos

Já implementado e testado localmente (servidor estático de desenvolvimento): cadastro de empresa/turnos/funcionários, geração heurística de escala, validação em tempo real, exportações (tela, impressão, CSV, PDF, backup) e persistência via SQLite/IndexedDB.

Publicado no GitHub Pages: https://danrolim.github.io/escala-5x2-contabilidade/ (repositório `danrolim/escala-5x2-contabilidade`, branch `main`).

Pendências de implementação (já descritas nas seções acima, ainda não atendidas pelo código):
1. Carga horária contratada individual por funcionário (5.2).
2. Importação de funcionários via CSV/Excel (5.2).
3. Exibição do nº de funcionários por turno (5.2).
4. Data de referência automática da fase da lei (5.1).

Próximo passo: testar com dados reais de uma empresa-cliente piloto da contabilidade.
