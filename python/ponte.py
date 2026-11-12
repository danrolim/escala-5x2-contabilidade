"""Camada de integração entre o JavaScript (js/app.js) e os módulos Python.

Todas as funções aqui recebem e retornam texto JSON, para simplificar a
travessia da fronteira Pyodide <-> JavaScript. É este módulo que o app.js
chama diretamente.
"""

import json

import gerador_escala
import persistencia
import validador
from regras import validar_carga_horaria_contratada

_conn = None


def inicializar():
    global _conn
    _conn = persistencia.conectar()
    return obter_estado()


def obter_estado():
    return json.dumps(
        {
            "empresa": persistencia.carregar_empresa(_conn),
            "funcionarios": persistencia.carregar_funcionarios(_conn),
            "escala": persistencia.carregar_escala(_conn),
        },
        ensure_ascii=False,
    )


def salvar_empresa(empresa_json):
    empresa = json.loads(empresa_json)
    ok, erro = validar_carga_horaria_contratada(
        empresa.get("carga_horaria_semanal"), empresa.get("fase_lei")
    )
    if not ok:
        return json.dumps({"ok": False, "erro": erro})
    persistencia.salvar_empresa(_conn, empresa)
    return json.dumps({"ok": True})


def salvar_funcionarios(funcionarios_json):
    funcionarios = json.loads(funcionarios_json)
    persistencia.salvar_funcionarios(_conn, funcionarios)
    return json.dumps({"ok": True})


def gerar_escala():
    empresa = persistencia.carregar_empresa(_conn)
    funcionarios = persistencia.carregar_funcionarios(_conn)
    if not empresa:
        return json.dumps({"ok": False, "erro": "Cadastre os dados da empresa antes de gerar a escala."})
    if not funcionarios:
        return json.dumps({"ok": False, "erro": "Cadastre ao menos um funcionário antes de gerar a escala."})
    if not empresa.get("turnos"):
        return json.dumps({"ok": False, "erro": "Cadastre ao menos um turno antes de gerar a escala."})

    escala = gerador_escala.gerar_escala(empresa, funcionarios)
    escala["violacoes"] = validador.validar_escala(empresa, funcionarios, escala)
    persistencia.salvar_escala(_conn, escala)
    return json.dumps({"ok": True, "escala": escala}, ensure_ascii=False)


def validar_escala_editada(escala_json):
    escala = json.loads(escala_json)
    empresa = persistencia.carregar_empresa(_conn)
    funcionarios = persistencia.carregar_funcionarios(_conn)
    escala["violacoes"] = validador.validar_escala(empresa, funcionarios, escala)
    persistencia.salvar_escala(_conn, escala)
    return json.dumps({"ok": True, "escala": escala}, ensure_ascii=False)


def exportar_backup():
    return persistencia.exportar_backup_json(_conn)


def importar_backup(texto_json):
    persistencia.importar_backup_json(_conn, texto_json)
    return obter_estado()
