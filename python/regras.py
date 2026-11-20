"""Parâmetros legais da escala 5x2 (EC 141/2026) e do descanso dominical.

Os valores abaixo são os parâmetros *padrão* sugeridos na tela de configuração,
não valores fixos de uso obrigatório — a empresa pode ajustar a carga horária
contratada (para baixo) e a fase da lei na própria interface.
"""

FASES_PADRAO = {
    "42h": {"limite_horas_semanais": 42, "vigencia_inicio": "2026-12-16"},
    "40h": {"limite_horas_semanais": 40, "vigencia_inicio": "2027-12-16"},
}


# Escala quinzenal do art. 386 da CLT: no setor GERAL, a mulher tem direito a
# folgar no domingo pelo menos uma vez a cada 15 dias — na prática, isso é uma
# escala alternada (trabalhou um domingo, o domingo seguinte tem que ser de
# folga), não "até 2 domingos seguidos trabalhados". Por isso o teto é 7 dias
# (1 semana), não 15: o mecanismo em gerador_escala.py força a folga assim que
# se passa 1 semana desde o último domingo de descanso.
PERIODO_DOMINGO_MULHER_DIAS = 7
PERIODO_DOMINGO_GERAL_DIAS = 49

# No COMÉRCIO (Lei 10.101/2000), é permitido trabalhar até 2 domingos
# seguidos antes de folgar um — tanto no padrão "trabalha 2, folga 1" quanto
# "trabalha 2, folga 2" (a folga adicional é só uma escolha de rodízio, não
# muda o teto). Isso vale para homens e mulheres: é uma exceção expressa à
# escala quinzenal alternada do art. 386 da CLT, que no comércio não se
# aplica — por isso o teto é 14 dias (2 semanas) independente do sexo, e
# periodo_maximo_domingo_dias() verifica o setor antes do sexo.
PERIODO_DOMINGO_COMERCIO_DIAS = 14


def limite_horas_fase(fase, fases=None):
    fases = fases or FASES_PADRAO
    config = fases.get(fase)
    if not config:
        raise ValueError(f"Fase de lei desconhecida: {fase}")
    return config["limite_horas_semanais"]


def periodo_maximo_domingo_dias(sexo, setor):
    """Maior intervalo permitido, em dias corridos, sem folga em domingo."""
    if setor == "comercio":
        return PERIODO_DOMINGO_COMERCIO_DIAS
    if sexo == "F":
        return PERIODO_DOMINGO_MULHER_DIAS
    return PERIODO_DOMINGO_GERAL_DIAS


def base_legal_domingo(sexo, setor):
    if setor == "comercio":
        return "Lei nº 10.101/2000 (comércio — exceção à escala quinzenal da mulher)"
    if sexo == "F":
        return "Art. 386 da CLT"
    return "Lei nº 605/1949"


def formatar_horas(horas):
    """Converte um valor decimal de horas (ex.: 8.4) em texto 'Xh' ou 'XhYYmin'."""
    total_minutos = round((horas or 0) * 60)
    h, m = divmod(total_minutos, 60)
    return f"{h}h" if m == 0 else f"{h}h{m:02d}min"


def validar_carga_horaria_contratada(carga_contratada, fase, fases=None):
    limite = limite_horas_fase(fase, fases)
    if carga_contratada is None:
        return False, "Informe a carga horária semanal contratada."
    if carga_contratada > limite:
        return False, (
            f"Carga horária contratada ({carga_contratada}h) excede o limite "
            f"legal da fase {fase} ({limite}h)."
        )
    if carga_contratada <= 0:
        return False, "A carga horária contratada deve ser maior que zero."
    return True, None
