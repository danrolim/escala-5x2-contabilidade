"""Gerador heurístico de escala 5x2, com revezamento dominical.

Não é um otimizador exato: é uma heurística (ver PRD.md, seção 6) que busca uma
distribuição que já nasça dentro da lei, em vez de gerar algo genérico e deixar
toda a conformidade para o ajuste manual. Prioridades, da mais alta para a mais
baixa:

1. Cobertura dos turnos escolhidos em cada dia (mínimo de cada turno).
2. Folgas: no máximo 2 por semana, domingo preferencial, limites legais de
   domingo trabalhado.
3. Turno fixo: cada funcionário começa no turno para o qual foi atribuído, mas
   pode ser deslocado para outro turno em que está apto, num dia específico,
   para cobrir uma falta (ver ``_alocar_dia``).

Dias da semana seguem a convenção de ``datetime.date.weekday()``:
0 = Segunda ... 6 = Domingo.
"""

from regras import formatar_horas, periodo_maximo_domingo_dias

DOMINGO = 6
SABADO = 5
SEMANAS_POR_ESCALA = 4
NOMES_DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _minimo(turno):
    return 2 if turno.get("revezamento") else 1


def _turnos_aptos(funcionario, turnos):
    permitidos = funcionario.get("turnos_permitidos") or []
    validos = {t["id"] for t in turnos}
    permitidos = [t_id for t_id in permitidos if t_id in validos]
    if not permitidos:
        return [t["id"] for t in turnos]
    return permitidos


def _componentes_turnos(turnos, funcionarios):
    pai = {t["id"]: t["id"] for t in turnos}

    def encontrar(x):
        while pai[x] != x:
            x = pai[x]
        return x

    for f in funcionarios:
        aptos = _turnos_aptos(f, turnos)
        for outro in aptos[1:]:
            ra, rb = encontrar(aptos[0]), encontrar(outro)
            if ra != rb:
                pai[ra] = rb

    grupos = {}
    for t in turnos:
        grupos.setdefault(encontrar(t["id"]), set()).add(t["id"])
    return list(grupos.values())


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
        aptos_ao_turno = sum(1 for f in funcionarios if turno["id"] in _turnos_aptos(f, turnos))
        if aptos_ao_turno < _minimo(turno):
            avisos.append(
                f"Turno '{turno['nome']}' tem apenas {aptos_ao_turno} funcionário(s) "
                f"apto(s) cadastrado(s); o mínimo necessário é {_minimo(turno)}."
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


def _montar_grupos(funcionarios, turnos, turno_atribuido, componentes):
    grupos = []
    ids_ordenados = [t["id"] for t in turnos]
    turno_por_id = {t["id"]: t for t in turnos}
    for comp in componentes:
        membros = [f["id"] for f in funcionarios if turno_atribuido.get(f["id"]) in comp]
        if not membros:
            continue
        grupos.append(
            {
                "membros": membros,
                "turnos": [
                    (t_id, _minimo(turno_por_id[t_id]), turno_por_id[t_id]["nome"])
                    for t_id in ids_ordenados
                    if t_id in comp
                ],
            }
        )
    return grupos


def _avisar_subdimensionamento(grupos, dias_trabalho_max, dias_funcionamento, avisos):
    for g in grupos:
        minimo_total = sum(minimo for _, minimo, _ in g["turnos"])
        necessario = len(dias_funcionamento) * minimo_total
        disponivel = sum(dias_trabalho_max.get(fid, 0) for fid in g["membros"])
        if disponivel < necessario:
            nomes = ", ".join(f"'{nome}'" for _, _, nome in g["turnos"])
            avisos.append(
                f"Turno(s) {nomes}: com a carga horária atual, os {len(g['membros'])} "
                f"funcionário(s) alocado(s) somam {disponivel} dia(s)-pessoa de trabalho por "
                f"semana, menos que os {necessario} necessários para manter a cobertura mínima "
                f"em todos os {len(dias_funcionamento)} dias de funcionamento. Considere alocar "
                f"mais funcionários a este turno."
            )


def _selecionar_trabalhadores_domingo(
    membros, minimo, sexo_por_fid, setor, dias_desde_domingo_livre, semana, avisos, nome_turno
):
    """Decide quem trabalha no domingo nesta semana para um turno.

    O padrão é todo mundo folgar no domingo (preferência do EC 141/2026); só o
    mínimo necessário é escolhido para trabalhar, girando semana a semana entre
    os candidatos. Prioriza quem ainda está dentro do próprio limite legal de
    dias sem descanso dominical; se não houver gente suficiente dentro do
    limite, usa quem tiver disponível e avisa.
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
    if not membros or minimo <= 0:
        return set()
    qtd = min(minimo, len(membros))
    inicio = (semana * qtd) % len(membros)
    return {membros[(inicio + k) % len(membros)] for k in range(qtd)}


def _trocar_folgas_semana(semana, fid_a, fid_b):
    folgas = semana["folgas"]
    folgas[fid_a], folgas[fid_b] = folgas[fid_b], folgas[fid_a]


def _distribuir_folgas_extra(membros_ids, offs_por_membro, faltam_por_membro, candidatos):
    """Distribui as folgas de dias de semana de um grupo, escolhendo sempre o dia
    candidato com menos folgas já atribuídas ao grupo — assim o mesmo dia não
    fica com folga de duas pessoas enquanto houver outro livre. Não depende da
    semana, então o padrão de folgas fixas se repete semana a semana.
    """
    if not candidatos:
        return

    carga = {d: 0 for d in range(7)}
    for fid in membros_ids:
        for d in offs_por_membro[fid]:
            carga[d] += 1

    for fid in membros_ids:
        for _ in range(faltam_por_membro.get(fid, 0)):
            livres = [d for d in candidatos if d not in offs_por_membro[fid]]
            if not livres:
                break
            escolhido = min(livres, key=lambda d: (carga[d], candidatos.index(d)))
            offs_por_membro[fid].add(escolhido)
            carga[escolhido] += 1


def _mover_para(alvo, atual, trabalhando, aptos_por_fid, minimo_por_turno, turnos_ids):
    """Acha um caminho de trocas que coloque mais um funcionário em ``alvo``,
    tirando-o de um turno que tem sobra (ou em cadeia, até achar sobra).
    Altera ``atual`` in-place e devolve False se não há como."""
    contagem = {t: 0 for t in turnos_ids}
    for fid in trabalhando:
        contagem[atual[fid]] += 1

    pai = {alvo: None}
    fila = [alvo]
    for x in fila:
        for fid in trabalhando:
            s = atual[fid]
            if s == x or x not in aptos_por_fid[fid] or s in pai:
                continue
            pai[s] = (x, fid)
            if contagem[s] > minimo_por_turno[s]:
                no = s
                while pai[no] is not None:
                    destino, w = pai[no]
                    atual[w] = destino
                    no = destino
                return True
            fila.append(s)
    return False


def _alocar_dia(trabalhando, aptos_por_fid, turnos_ids, minimo_por_turno):
    """Distribui os funcionários que trabalham no dia pelos turnos em que estão
    aptos, priorizando cobrir o mínimo de cada turno. Começa com cada um no
    próprio turno (fixo) e só troca quando algum turno ficaria abaixo do mínimo."""
    atual = {fid: aptos_por_fid[fid][0] for fid in trabalhando}
    for alvo in turnos_ids:
        while sum(1 for fid in trabalhando if atual[fid] == alvo) < minimo_por_turno[alvo]:
            if not _mover_para(alvo, atual, trabalhando, aptos_por_fid, minimo_por_turno, turnos_ids):
                break
    return atual


def _recalcular_alocacao(
    semana, idx, funcionarios, aptos_por_fid, turnos_ids, minimo_por_turno, turno_por_id, dias_funcionamento, avisos
):
    alocacao = {}
    for dia in dias_funcionamento:
        trabalhando = [
            f["id"]
            for f in funcionarios
            if f["id"] in aptos_por_fid and dia not in semana["folgas"][f["id"]]
        ]
        atual = _alocar_dia(trabalhando, aptos_por_fid, turnos_ids, minimo_por_turno)
        alocacao_dia = {t: [] for t in turnos_ids}
        for fid in trabalhando:
            alocacao_dia[atual[fid]].append(fid)
        for t in turnos_ids:
            n = len(alocacao_dia[t])
            if n < minimo_por_turno[t]:
                avisos.append(
                    f"Semana {idx + 1}, {NOMES_DIAS[dia]}, turno '{turno_por_id[t]['nome']}': "
                    f"{n} funcionário(s) escalado(s), mínimo exigido é {minimo_por_turno[t]}."
                )
        alocacao[dia] = alocacao_dia
    semana["turnos"] = alocacao


def _gerar_semanas_ciclo(
    funcionarios,
    grupos,
    aptos_por_fid,
    dias_trabalho_max,
    dias_fechados,
    dias_candidatos_fixos,
    funciona_domingo,
    funciona_sabado,
    setor,
    sexo_por_fid,
    estado_inicial,
    ciclo_semanas,
    avisos,
):
    """Gera as folgas de ``ciclo_semanas`` semanas a partir de um estado inicial
    de "dias desde o último domingo de descanso" por funcionário. A alocação
    diária por turno é calculada depois, a partir das folgas (ver
    ``_recalcular_alocacao``). Devolve as semanas e o estado final."""
    dias_desde_domingo_livre = dict(estado_inicial)
    semanas = []

    for semana in range(ciclo_semanas):
        domingo_trabalhadores = set()
        sabado_trabalhadores = set()
        for g in grupos:
            for t_id, minimo, nome in g["turnos"]:
                candidatos = [
                    fid
                    for fid in g["membros"]
                    if t_id in aptos_por_fid[fid]
                    and dias_trabalho_max.get(fid, 0) > 0
                    and fid not in domingo_trabalhadores
                ]
                if funciona_domingo:
                    domingo_trabalhadores |= _selecionar_trabalhadores_domingo(
                        candidatos, minimo, sexo_por_fid, setor, dias_desde_domingo_livre, semana, avisos, nome
                    )
                if funciona_sabado:
                    candidatos_sab = [
                        fid
                        for fid in g["membros"]
                        if t_id in aptos_por_fid[fid]
                        and dias_trabalho_max.get(fid, 0) > 0
                        and fid not in sabado_trabalhadores
                    ]
                    sabado_trabalhadores |= _selecionar_trabalhadores_sabado(candidatos_sab, minimo, semana)

        offs_por_funcionario = {}
        faltam_por_funcionario = {}

        for f in funcionarios:
            fid = f["id"]
            if fid not in aptos_por_fid:
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
                candidatos_remocao = [d for d in (SABADO, DOMINGO) if d in offs]
                for dia in candidatos_remocao:
                    if excesso <= 0:
                        break
                    offs.discard(dia)
                    excesso -= 1

        for g in grupos:
            faltam_grupo = {fid: faltam_por_funcionario[fid] for fid in g["membros"]}
            _distribuir_folgas_extra(g["membros"], offs_por_funcionario, faltam_grupo, dias_candidatos_fixos)

        semanas.append(
            {
                "folgas": {fid: sorted(d) for fid, d in offs_por_funcionario.items()},
                "turnos": {},
            }
        )

        if funciona_domingo:
            for f in funcionarios:
                if DOMINGO in offs_por_funcionario[f["id"]]:
                    dias_desde_domingo_livre[f["id"]] = 0
                else:
                    dias_desde_domingo_livre[f["id"]] += 7

    return semanas, dias_desde_domingo_livre


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
    turnos_ids = [t["id"] for t in turnos]
    minimo_por_turno = {t["id"]: _minimo(t) for t in turnos}
    carga_contratada = empresa.get("carga_horaria_semanal") or 0
    funciona_sabado = SABADO in dias_funcionamento
    dias_candidatos_fixos = [d for d in dias_funcionamento if d not in (SABADO, DOMINGO)]

    avisos = []
    turno_atribuido = _atribuir_turno_fixo(funcionarios, turnos, avisos)
    aptos_por_fid = {}
    for f in funcionarios:
        home = turno_atribuido.get(f["id"])
        if home is None:
            continue
        aptos_por_fid[f["id"]] = [home] + [t for t in _turnos_aptos(f, turnos) if t != home]

    dias_trabalho_max = _dias_trabalho_maximo(
        funcionarios, turno_atribuido, turno_por_id, carga_contratada, dias_funcionamento, avisos
    )
    componentes = _componentes_turnos(turnos, funcionarios)
    grupos = _montar_grupos(funcionarios, turnos, turno_atribuido, componentes)
    _avisar_subdimensionamento(grupos, dias_trabalho_max, dias_funcionamento, avisos)

    ciclo_semanas = SEMANAS_POR_ESCALA
    sexo_por_fid = {f["id"]: f["sexo"] for f in funcionarios}
    estado_inicial = {f["id"]: i * 7 for i, f in enumerate(funcionarios)}

    semanas, dias_desde_domingo_livre = _gerar_semanas_ciclo(
        funcionarios,
        grupos,
        aptos_por_fid,
        dias_trabalho_max,
        dias_fechados,
        dias_candidatos_fixos,
        funciona_domingo,
        funciona_sabado,
        setor,
        sexo_por_fid,
        estado_inicial,
        ciclo_semanas,
        avisos,
    )

    # A escala é pensada para ser reaplicada em repetição (o mesmo ciclo volta
    # a valer depois da última semana) — por isso a "virada" do fim deste ciclo
    # para a semana 1 do próximo tem que respeitar o mesmo teto legal de
    # domingos seguidos. Repete uma passada pelas semanas, carregando o estado
    # real de dias-sem-domingo de cada funcionário como ponto de partida da
    # semana 1; quem estourar é trocado (folga inteira) por um colega do mesmo
    # grupo dentro do limite. Repete a passada até não precisar trocar mais
    # ninguém; sem ninguém disponível, só avisa.
    if funciona_domingo and semanas:
        nomes_por_fid = {f["id"]: f["nome"] for f in funcionarios}

        def _passada_de_reparo(estado_inicial_passada, avisos_destino):
            estado = dict(estado_inicial_passada)
            mudou = False
            for semana in semanas:
                for g in grupos:
                    trabalhando = {fid for fid in g["membros"] if DOMINGO not in semana["folgas"][fid]}
                    descansando = set(g["membros"]) - trabalhando
                    for fid_a in sorted(trabalhando):
                        periodo_max_a = periodo_maximo_domingo_dias(sexo_por_fid[fid_a], setor)
                        if estado[fid_a] + 7 <= periodo_max_a:
                            continue
                        candidatos = [
                            fid_b
                            for fid_b in sorted(descansando)
                            if dias_trabalho_max.get(fid_b, 0) == dias_trabalho_max.get(fid_a, 0)
                            and estado[fid_b] + 7 <= periodo_maximo_domingo_dias(sexo_por_fid[fid_b], setor)
                        ]
                        if not candidatos:
                            avisos_destino.append(
                                f"Ao repetir este ciclo de {ciclo_semanas} semanas, "
                                f"'{nomes_por_fid[fid_a]}' ficaria sem domingo de descanso há mais de "
                                f"{periodo_max_a} dias na virada do ciclo. Não há colega do grupo "
                                f"dentro do limite para alternar; considere alocar mais funcionários "
                                f"a este turno."
                            )
                            continue
                        fid_b = candidatos[0]
                        _trocar_folgas_semana(semana, fid_a, fid_b)
                        trabalhando.discard(fid_a)
                        trabalhando.add(fid_b)
                        descansando.discard(fid_b)
                        descansando.add(fid_a)
                        mudou = True
                for fid in estado:
                    if DOMINGO in semana["folgas"][fid]:
                        estado[fid] = 0
                    else:
                        estado[fid] += 7
            return estado, mudou

        estado = dict(dias_desde_domingo_livre)
        convergiu = False
        for _ in range(20):
            estado, mudou = _passada_de_reparo(estado, [])
            if not mudou:
                convergiu = True
                break
        if not convergiu:
            avisos.append(
                "Não foi possível acomodar a repetição deste ciclo sem que alguém acabe "
                "ultrapassando o limite legal de domingos seguidos trabalhados em algum "
                "momento da repetição — o quadro de algum turno de revezamento é pequeno "
                "demais para sustentar a alternância indefinidamente, não importa como as "
                "folgas sejam distribuídas. Considere alocar mais funcionários aos turnos "
                "de revezamento; a validação sinaliza onde a violação residual aparece."
            )
        _passada_de_reparo(estado, avisos)

    for idx, semana in enumerate(semanas):
        _recalcular_alocacao(
            semana,
            idx,
            funcionarios,
            aptos_por_fid,
            turnos_ids,
            minimo_por_turno,
            turno_por_id,
            dias_funcionamento,
            avisos,
        )

    return {
        "ciclo_semanas": ciclo_semanas,
        "semanas": semanas,
        "avisos": avisos,
    }
