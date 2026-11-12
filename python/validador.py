"""Validação de uma escala (gerada ou ajustada manualmente) contra as regras legais.

Funciona de forma independente do gerador: pode validar tanto a escala recém
gerada quanto uma versão editada manualmente na tela, recalculando tudo do zero
a partir da estrutura ``{"semanas": [...]}``.
"""

from regras import base_legal_domingo, formatar_horas, periodo_maximo_domingo_dias

DOMINGO = 6


def validar_escala(empresa, funcionarios, escala):
    turnos_por_id = {t["id"]: t for t in empresa["turnos"]}
    carga_contratada = empresa.get("carga_horaria_semanal")
    setor = empresa.get("setor", "geral")

    violacoes = []
    dias_desde_domingo_livre = {f["id"]: 0 for f in funcionarios}

    for num_semana, semana in enumerate(escala["semanas"]):
        folgas = semana.get("folgas", {})
        turnos_dia = semana.get("turnos", {})

        for f in funcionarios:
            fid = f["id"]
            folgas_fid = folgas.get(fid, [])

            qtd_folgas = len(folgas_fid)
            if qtd_folgas < 2:
                violacoes.append(
                    {
                        "funcionario_id": fid,
                        "funcionario_nome": f["nome"],
                        "semana": num_semana + 1,
                        "dia": None,
                        "nivel": "erro",
                        "mensagem": (
                            f"Apenas {qtd_folgas} dia(s) de descanso na semana "
                            f"{num_semana + 1} (mínimo exigido: 2)."
                        ),
                        "base_legal": "EC 141/2026",
                    }
                )

            domingo_de_folga = DOMINGO in folgas_fid
            if domingo_de_folga:
                dias_desde_domingo_livre[fid] = 0
            else:
                dias_desde_domingo_livre[fid] += 7
                periodo_max = periodo_maximo_domingo_dias(f["sexo"], setor)
                if dias_desde_domingo_livre[fid] > periodo_max:
                    violacoes.append(
                        {
                            "funcionario_id": fid,
                            "funcionario_nome": f["nome"],
                            "semana": num_semana + 1,
                            "dia": DOMINGO,
                            "nivel": "erro",
                            "mensagem": (
                                f"Sem domingo de descanso há mais de "
                                f"{periodo_max} dias."
                            ),
                            "base_legal": base_legal_domingo(f["sexo"], setor),
                        }
                    )

            horas_semana = sum(
                turnos_por_id.get(turno_id, {}).get("horas_por_dia", 0)
                for turnos_alocados in turnos_dia.values()
                for turno_id, fids in turnos_alocados.items()
                if fid in fids
            )
            if carga_contratada and horas_semana > carga_contratada + 1e-6:
                violacoes.append(
                    {
                        "funcionario_id": fid,
                        "funcionario_nome": f["nome"],
                        "semana": num_semana + 1,
                        "dia": None,
                        "nivel": "erro",
                        "mensagem": (
                            f"Carga horária na semana {num_semana + 1}: "
                            f"{formatar_horas(horas_semana)}, acima das "
                            f"{formatar_horas(carga_contratada)} contratadas pela empresa."
                        ),
                        "base_legal": "EC 141/2026",
                    }
                )

        for dia, turnos_alocados in turnos_dia.items():
            for turno_id, fids in turnos_alocados.items():
                turno = turnos_por_id.get(turno_id)
                if not turno:
                    continue
                minimo = 2 if turno.get("revezamento") else 1
                if len(fids) < minimo:
                    violacoes.append(
                        {
                            "funcionario_id": None,
                            "funcionario_nome": None,
                            "semana": num_semana + 1,
                            "dia": dia,
                            "turno_id": turno_id,
                            "nivel": "alerta",
                            "mensagem": (
                                f"Dia {dia}, turno '{turno['nome']}': "
                                f"{len(fids)} funcionário(s) alocado(s), "
                                f"mínimo exigido é {minimo}."
                            ),
                            "base_legal": "Revezamento de turnos (mínimo 2 por turno)",
                        }
                    )

    return violacoes
