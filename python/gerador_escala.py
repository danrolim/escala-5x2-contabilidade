"""Gerador heurístico de escala 5x2, com revezamento dominical.

Não é um otimizador exato: é uma heurística (ver PRD.md, seção 6) que busca uma
distribuição que já nasça dentro da lei, em vez de gerar algo genérico e deixar
toda a conformidade para o ajuste manual. Para isso:

- Cada funcionário é fixado em UM turno (entre os que ele é apto a atuar),
  balanceando a quantidade de pessoas por turno — evita que a mesma pessoa
  apareça em turnos diferentes em dias diferentes, o que não reflete a prática
  real de escalas fixas.
- A quantidade de dias trabalhados por semana de cada funcionário é limitada
  pela carga horária contratada dividida pelas horas do turno dele, não apenas
  pelo mínimo de 2 folgas — isso evita o estouro de carga horária.
- Cada funcionário tem **no máximo 2 folgas por semana** (os dias em que a
  empresa fecha já contam dentro dessas 2, não se soma folga extra além
  disso) — a única exceção é quando a carga horária contratada força mais
  folga do que isso (turno mais longo que o necessário para os dias de
  funcionamento).
- Sábado e domingo (quando a empresa funciona neles) são, por padrão,
  as 2 folgas de todo mundo; só o mínimo necessário por turno é escalado
  para trabalhar nesses dias, girando entre os colegas semana a semana —
  quem é escalado troca a folga de sábado/domingo por um dia de semana,
  sem ultrapassar as 2 folgas totais.
- Os dias de folga "extras" de dias de semana (quando a carga horária exige
  mais de 2, ou quando sábado/domingo foi trocado por um dia de semana) são
  distribuídos em rodízio ENTRE OS COLEGAS DE TURNO (round-robin "tipo
  baralho"), não de forma independente por pessoa — isso mantém, sempre que
  o quadro de funcionários permitir, o mínimo de pessoas por turno em todos
  os dias, em vez de vários funcionários coincidirem a folga no mesmo dia.

Dias da semana seguem a convenção de ``datetime.date.weekday()``:
0 = Segunda ... 6 = Domingo.
"""

from regras import formatar_horas, periodo_maximo_domingo_dias

DOMINGO = 6
SABADO = 5
SEMANAS_POR_ESCALA = 4


def _turnos_aptos(funcionario, turnos):
    permitidos = funcionario.get("turnos_permitidos") or []
    validos = {t["id"] for t in turnos}
    permitidos = [t_id for t_id in permitidos if t_id in validos]
    if not permitidos:
        return [t["id"] for t in turnos]
    return permitidos


def _atribuir_turno_fixo(funcionarios, turnos, avisos):
    contagem = {t["id"]: 0 for t in turnos}
    atribuicao = {}
    for f in funcionarios:
        aptos = _turnos_aptos(f, turnos)
        if not aptos:
            avisos.append(f"'{f['nome']}' não é apto a nenhum turno cadastrado; não foi escalado.")
            continue
        escolhido = min(aptos, key=lambda t_id: contagem[t_id])
        atribuicao[f["id"]] = escolhido
        contagem[escolhido] += 1

    for turno in turnos:
        minimo = 2 if turno.get("revezamento") else 1
        if contagem[turno["id"]] < minimo:
            avisos.append(
                f"Turno '{turno['nome']}' tem apenas {contagem[turno['id']]} funcionário(s) "
                f"apto(s) cadastrado(s); o mínimo necessário é {minimo}."
            )
    return atribuicao


def _dias_trabalho_maximo(funcionarios, turno_atribuido, turno_por_id, carga_contratada, dias_funcionamento, avisos):
    maximo = {}
    for f in funcionarios:
        turno_id = turno_atribuido.get(f["id"])
        if not turno_id:
            maximo[f["id"]] = 0
            continue
        horas_turno = turno_por_id[turno_id].get("horas_por_dia", 0)
        if not carga_contratada or horas_turno <= 0:
            maximo[f["id"]] = len(dias_funcionamento)
            continue
        # +1e-9 evita que erros de ponto flutuante (ex.: 42 / 8.4) derrubem um
        # resultado que deveria ser exato (5 dias) para o inteiro anterior (4).
        dias_por_horas = int(carga_contratada / horas_turno + 1e-9)
        valor = max(0, min(len(dias_funcionamento), dias_por_horas))
        maximo[f["id"]] = valor
        if dias_por_horas < len(dias_funcionamento):
            avisos.append(
                f"'{f['nome']}': o turno de {formatar_horas(horas_turno)}/dia permite no máximo "
                f"{dias_por_horas} dia(s) de trabalho dentro das {formatar_horas(carga_contratada)} "
                f"contratadas (a empresa funciona {len(dias_funcionamento)} dia(s) por semana)."
            )
        if dias_por_horas <= 0:
            avisos.append(
                f"'{f['nome']}': a carga horária contratada ({formatar_horas(carga_contratada)}) não "
                f"comporta nenhum dia inteiro no turno de {formatar_horas(horas_turno)}/dia."
            )
    return maximo


def _avisar_subdimensionamento(funcionarios, turnos, turno_atribuido, dias_trabalho_max, dias_funcionamento, avisos):
    for turno in turnos:
        membros = [f for f in funcionarios if turno_atribuido.get(f["id"]) == turno["id"]]
        if not membros:
            continue
        minimo = 2 if turno.get("revezamento") else 1
        necessario = len(dias_funcionamento) * minimo
        disponivel = sum(dias_trabalho_max.get(f["id"], 0) for f in membros)
        if disponivel < necessario:
            avisos.append(
                f"Turno '{turno['nome']}': com a carga horária atual, os {len(membros)} "
                f"funcionário(s) alocado(s) somam {disponivel} dia(s)-pessoa de trabalho por "
                f"semana, menos que os {necessario} necessários para manter {minimo} "
                f"funcionário(s) em todos os {len(dias_funcionamento)} dias de funcionamento. "
                f"Considere alocar mais funcionários a este turno."
            )


def _selecionar_trabalhadores_domingo(
    membros, minimo, sexo_por_fid, setor, dias_desde_domingo_livre, semana, avisos, nome_turno
):
    """Decide quem trabalha no domingo nesta semana.

    O padrão é todo mundo folgar no domingo (preferência do EC 141/2026); só o
    mínimo necessário para cobrir o turno é escalado para trabalhar, com a
    escolha girando semana a semana entre os colegas de turno. Prioriza quem
    ainda está dentro do próprio limite legal de dias sem descanso dominical
    (diferente para mulheres, geral e comércio); se não houver gente
    suficiente dentro do limite, usa quem tiver disponível e avisa.
    """
    if not membros or minimo <= 0:
        return set()

    elegiveis = [
        fid
        for fid in membros
        if dias_desde_domingo_livre[fid] + 7 <= periodo_maximo_domingo_dias(sexo_por_fid[fid], setor)
    ]
    qtd = min(minimo, len(membros))
    pool = elegiveis if len(elegiveis) >= qtd else membros
    if len(elegiveis) < qtd:
        avisos.append(
            f"Turno '{nome_turno}': não há funcionário(s) suficiente(s) dentro do limite legal "
            f"de descanso dominical para cobrir o domingo da semana {semana + 1}; ao menos um "
            f"funcionário terá que trabalhar além do período de descanso devido. Considere "
            f"alocar mais funcionários a este turno."
        )

    inicio = (semana * qtd) % len(pool)
    return {pool[(inicio + k) % len(pool)] for k in range(qtd)}


def _selecionar_trabalhadores_sabado(membros, minimo, semana):
    """Decide quem trabalha no sábado nesta semana.

    Mesmo princípio do domingo (``_selecionar_trabalhadores_domingo``): o
    padrão é todo mundo folgar no sábado, e só o mínimo necessário é escalado
    para trabalhar, girando entre os colegas de turno semana a semana. Sem
    teto legal aqui (não existe regra específica para sábado), então a
    rotação é só um rodízio simples.
    """
    if not membros or minimo <= 0:
        return set()
    qtd = min(minimo, len(membros))
    inicio = (semana * qtd) % len(membros)
    return {membros[(inicio + k) % len(membros)] for k in range(qtd)}


def _distribuir_folgas_extra(membros_ids, offs_por_membro, faltam_por_membro, candidatos):
    """Distribui as folgas 'extras' de um grupo (colegas do mesmo turno) em
    rodízio, para manter o máximo de pessoas simultaneamente disponíveis em
    cada dia, em vez de cada um escolher seus dias de folga de forma isolada.

    Não depende da semana: a mesma posição de cada funcionário na fila sempre
    mapeia para o mesmo dia candidato, então o padrão de folgas se repete
    identicamente semana a semana (folgas em dias fixos), que é o que se pede
    quando a empresa não tem domingo em rodízio obrigando variação. O domingo
    nunca entra nesta lista de candidatos (ver chamada em ``gerar_escala``) —
    ele é tratado à parte, apenas pelo rodízio legal obrigatório.
    """
    if not candidatos:
        return

    fila = []
    restante = dict(faltam_por_membro)
    progresso = True
    while progresso:
        progresso = False
        for fid in membros_ids:
            if restante.get(fid, 0) > 0:
                fila.append(fid)
                restante[fid] -= 1
                progresso = True

    total_dias = len(candidatos)
    for posicao, fid in enumerate(fila):
        indice = posicao % total_dias
        tentativas = 0
        while candidatos[indice] in offs_por_membro[fid] and tentativas < total_dias:
            indice = (indice + 1) % total_dias
            tentativas += 1
        offs_por_membro[fid].add(candidatos[indice])


def gerar_escala(empresa, funcionarios):
    """
    empresa: {
        "dias_funcionamento": [0..6, ...],
        "setor": "geral" | "comercio",
        "carga_horaria_semanal": float,
        "turnos": [{"id", "nome", "horas_por_dia", "revezamento": bool}, ...],
    }
    funcionarios: [{"id", "nome", "sexo": "M"|"F", "turnos_permitidos": [id, ...]}, ...]

    Retorna {
        "ciclo_semanas": int,
        "semanas": [
            {
                "folgas": {funcionario_id: [dia, ...]},
                "turnos": {dia: {turno_id: [funcionario_id, ...]}},
            },
            ...
        ],
        "avisos": [str, ...],
    }
    """
    dias_funcionamento = sorted(set(empresa["dias_funcionamento"]))
    dias_fechados = [d for d in range(7) if d not in dias_funcionamento]
    funciona_domingo = DOMINGO in dias_funcionamento
    setor = empresa.get("setor", "geral")
    turnos = empresa["turnos"]
    turno_por_id = {t["id"]: t for t in turnos}
    carga_contratada = empresa.get("carga_horaria_semanal") or 0
    funciona_sabado = SABADO in dias_funcionamento
    dias_candidatos_fixos = [d for d in dias_funcionamento if d not in (SABADO, DOMINGO)]

    avisos = []
    turno_atribuido = _atribuir_turno_fixo(funcionarios, turnos, avisos)
    dias_trabalho_max = _dias_trabalho_maximo(
        funcionarios, turno_atribuido, turno_por_id, carga_contratada, dias_funcionamento, avisos
    )
    _avisar_subdimensionamento(funcionarios, turnos, turno_atribuido, dias_trabalho_max, dias_funcionamento, avisos)

    membros_por_turno = {}
    for f in funcionarios:
        t_id = turno_atribuido.get(f["id"])
        if t_id is None:
            continue
        membros_por_turno.setdefault(t_id, []).append(f["id"])

    ciclo_semanas = SEMANAS_POR_ESCALA
    dias_desde_domingo_livre = {f["id"]: i * 7 for i, f in enumerate(funcionarios)}
    sexo_por_fid = {f["id"]: f["sexo"] for f in funcionarios}

    semanas = []

    for semana in range(ciclo_semanas):
        domingo_trabalhadores = set()
        sabado_trabalhadores = set()
        for turno_id, membros in membros_por_turno.items():
            minimo = 2 if turno_por_id[turno_id].get("revezamento") else 1
            membros_disponiveis = [fid for fid in membros if dias_trabalho_max.get(fid, 0) > 0]
            if funciona_domingo:
                domingo_trabalhadores |= _selecionar_trabalhadores_domingo(
                    membros_disponiveis,
                    minimo,
                    sexo_por_fid,
                    setor,
                    dias_desde_domingo_livre,
                    semana,
                    avisos,
                    turno_por_id[turno_id]["nome"],
                )
            if funciona_sabado:
                sabado_trabalhadores |= _selecionar_trabalhadores_sabado(membros_disponiveis, minimo, semana)

        offs_por_funcionario = {}
        faltam_por_funcionario = {}

        for f in funcionarios:
            fid = f["id"]
            if turno_atribuido.get(fid) is None:
                offs_por_funcionario[fid] = set(range(7))
                faltam_por_funcionario[fid] = 0
                continue

            offs = set(dias_fechados)
            if funciona_domingo and fid not in domingo_trabalhadores:
                offs.add(DOMINGO)  # preferencialmente, o domingo é dia de folga (EC 141/2026)
            if funciona_sabado and fid not in sabado_trabalhadores:
                offs.add(SABADO)  # idem: sábado por padrão é folga, só quem está na vez trabalha

            # No máximo 2 folgas por semana (dias em que a empresa fecha já contam
            # dentro dessas 2 — não se soma folga extra além disso), a menos que a
            # carga horária contratada force mais folga do que isso.
            offs_desejadas = max(2, 7 - dias_trabalho_max.get(fid, 0))
            offs_por_funcionario[fid] = offs
            faltam_por_funcionario[fid] = max(0, offs_desejadas - len(offs))
            excesso = len(offs) - offs_desejadas
            if excesso > 0:
                # domingo/sábado por padrão já davam folga além do necessário
                # (ex.: carga horária permite trabalhar os 2); tira o que sobrar,
                # priorizando manter o domingo como folga quando possível.
                candidatos_remocao = [d for d in (SABADO, DOMINGO) if d in offs]
                for dia in candidatos_remocao:
                    if excesso <= 0:
                        break
                    offs.discard(dia)
                    excesso -= 1

        for turno_id, membros in membros_por_turno.items():
            faltam_grupo = {fid: faltam_por_funcionario[fid] for fid in membros}
            _distribuir_folgas_extra(membros, offs_por_funcionario, faltam_grupo, dias_candidatos_fixos)

        alocacao_semana = {}
        for dia in dias_funcionamento:
            alocacao_dia = {t["id"]: [] for t in turnos}
            for f in funcionarios:
                t_id = turno_atribuido.get(f["id"])
                if t_id and dia not in offs_por_funcionario[f["id"]]:
                    alocacao_dia[t_id].append(f["id"])
            for turno in turnos:
                minimo = 2 if turno.get("revezamento") else 1
                if len(alocacao_dia[turno["id"]]) < minimo:
                    avisos.append(
                        f"Semana {semana + 1}, dia {dia}, turno '{turno['nome']}': "
                        f"{len(alocacao_dia[turno['id']])} funcionário(s) escalado(s), "
                        f"mínimo exigido é {minimo}."
                    )
            alocacao_semana[dia] = alocacao_dia

        semanas.append(
            {
                "folgas": {fid: sorted(d) for fid, d in offs_por_funcionario.items()},
                "turnos": alocacao_semana,
            }
        )

        if funciona_domingo:
            for f in funcionarios:
                if DOMINGO in offs_por_funcionario[f["id"]]:
                    dias_desde_domingo_livre[f["id"]] = 0
                else:
                    dias_desde_domingo_livre[f["id"]] += 7

    return {
        "ciclo_semanas": ciclo_semanas,
        "semanas": semanas,
        "avisos": avisos,
    }
