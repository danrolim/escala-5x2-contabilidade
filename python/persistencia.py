"""Persistência local via SQLite.

O arquivo do banco (``/escala.db``) vive no sistema de arquivos virtual do
Pyodide; é o lado JavaScript (``js/app.js``) que lê os bytes desse arquivo e os
guarda no IndexedDB do navegador após cada alteração, e os restaura ao abrir a
aplicação novamente no mesmo navegador.
"""

import json
import sqlite3

CAMINHO_DB = "/escala.db"


def conectar(caminho=CAMINHO_DB):
    conn = sqlite3.connect(caminho)
    criar_schema(conn)
    return conn


def criar_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS empresa (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome TEXT,
            setor TEXT,
            fase_lei TEXT,
            carga_horaria_semanal REAL,
            dias_funcionamento TEXT,
            turnos TEXT
        );
        CREATE TABLE IF NOT EXISTS funcionario (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            sexo TEXT NOT NULL,
            turnos_permitidos TEXT
        );
        CREATE TABLE IF NOT EXISTS escala_gerada (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            dados TEXT
        );
        """
    )
    conn.commit()


def salvar_empresa(conn, empresa):
    conn.execute(
        """
        INSERT INTO empresa (id, nome, setor, fase_lei, carga_horaria_semanal, dias_funcionamento, turnos)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            setor = excluded.setor,
            fase_lei = excluded.fase_lei,
            carga_horaria_semanal = excluded.carga_horaria_semanal,
            dias_funcionamento = excluded.dias_funcionamento,
            turnos = excluded.turnos
        """,
        (
            empresa.get("nome", ""),
            empresa["setor"],
            empresa["fase_lei"],
            empresa["carga_horaria_semanal"],
            json.dumps(empresa["dias_funcionamento"]),
            json.dumps(empresa["turnos"]),
        ),
    )
    conn.commit()


def carregar_empresa(conn):
    row = conn.execute(
        "SELECT nome, setor, fase_lei, carga_horaria_semanal, dias_funcionamento, turnos "
        "FROM empresa WHERE id = 1"
    ).fetchone()
    if not row:
        return None
    nome, setor, fase_lei, carga, dias_json, turnos_json = row
    return {
        "nome": nome,
        "setor": setor,
        "fase_lei": fase_lei,
        "carga_horaria_semanal": carga,
        "dias_funcionamento": json.loads(dias_json),
        "turnos": json.loads(turnos_json),
    }


def salvar_funcionarios(conn, funcionarios):
    conn.execute("DELETE FROM funcionario")
    # INSERT OR REPLACE em vez de INSERT puro: se a lista vinda do front-end
    # tiver algum id duplicado (ex.: estado da UI temporariamente inconsistente),
    # o último da lista prevalece em vez de travar a aplicação inteira com um
    # IntegrityError não tratado.
    conn.executemany(
        "INSERT OR REPLACE INTO funcionario (id, nome, sexo, turnos_permitidos) VALUES (?, ?, ?, ?)",
        [
            (f["id"], f["nome"], f["sexo"], json.dumps(f.get("turnos_permitidos", [])))
            for f in funcionarios
        ],
    )
    conn.commit()


def carregar_funcionarios(conn):
    rows = conn.execute(
        "SELECT id, nome, sexo, turnos_permitidos FROM funcionario"
    ).fetchall()
    return [
        {"id": r[0], "nome": r[1], "sexo": r[2], "turnos_permitidos": json.loads(r[3])}
        for r in rows
    ]


def salvar_escala(conn, escala):
    conn.execute(
        """
        INSERT INTO escala_gerada (id, dados) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET dados = excluded.dados
        """,
        (json.dumps(escala, ensure_ascii=False),),
    )
    conn.commit()


def carregar_escala(conn):
    row = conn.execute("SELECT dados FROM escala_gerada WHERE id = 1").fetchone()
    return json.loads(row[0]) if row else None


def exportar_backup_json(conn):
    return json.dumps(
        {
            "empresa": carregar_empresa(conn),
            "funcionarios": carregar_funcionarios(conn),
            "escala": carregar_escala(conn),
        },
        ensure_ascii=False,
    )


def importar_backup_json(conn, texto_json):
    dados = json.loads(texto_json)
    if dados.get("empresa"):
        salvar_empresa(conn, dados["empresa"])
    if dados.get("funcionarios") is not None:
        salvar_funcionarios(conn, dados["funcionarios"])
    if dados.get("escala") is not None:
        salvar_escala(conn, dados["escala"])
