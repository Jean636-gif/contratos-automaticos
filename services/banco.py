import sqlite3
from datetime import datetime, timezone

def conectar():
    return sqlite3.connect("banco.db", check_same_thread=False)

def agora_iso():
    return datetime.now(timezone.utc).isoformat()

def _coluna_existe(conn, tabela: str, coluna: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({tabela})")
    cols = [r[1] for r in cur.fetchall()]
    return coluna in cols

def _garantir_coluna(conn, tabela: str, coluna: str, tipo_sql: str):
    if not _coluna_existe(conn, tabela, coluna):
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo_sql}")
        conn.commit()

def criar_tabelas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha TEXT,
        perfil TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contratos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT,
        cnpj TEXT,
        razao_social TEXT,
        status TEXT,
        arquivo TEXT
    )
    """)
    conn.commit()

    # colunas extras em contratos
    _garantir_coluna(conn, "contratos", "fornecedor_cnpj", "TEXT")
    _garantir_coluna(conn, "contratos", "fornecedor_razao", "TEXT")
    _garantir_coluna(conn, "contratos", "versao", "INTEGER")
    _garantir_coluna(conn, "contratos", "tipo_modelo", "TEXT")
    _garantir_coluna(conn, "contratos", "criado_em", "TEXT")
    _garantir_coluna(conn, "contratos", "atualizado_em", "TEXT")
    _garantir_coluna(conn, "contratos", "finalizado_em", "TEXT")

    # soft delete + auditoria
    _garantir_coluna(conn, "contratos", "excluido_em", "TEXT")
    _garantir_coluna(conn, "contratos", "excluido_por", "TEXT")
    _garantir_coluna(conn, "contratos", "excluido_justificativa", "TEXT")

    # status_log para SLA
    cur.execute("""
    CREATE TABLE IF NOT EXISTS status_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrato_id INTEGER,
        de_status TEXT,
        para_status TEXT,
        alterado_em TEXT,
        alterado_por TEXT
    )
    """)
    conn.commit()
    conn.close()

def _proxima_versao_fornecedor(conn, fornecedor_cnpj: str) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(MAX(COALESCE(versao,0)), 0) + 1
        FROM contratos
        WHERE fornecedor_cnpj = ?
          AND (excluido_em IS NULL OR excluido_em = '')
        """,
        (fornecedor_cnpj,),
    )
    return int(cur.fetchone()[0])

def inserir_contrato_fornecedor(fornecedor_cnpj: str, fornecedor_razao: str, status: str, tipo_modelo: str) -> int:
    conn = conectar()
    conn.execute("BEGIN")
    try:
        versao = _proxima_versao_fornecedor(conn, fornecedor_cnpj)
        ts = agora_iso()

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO contratos (
                cnpj, razao_social, status, arquivo,
                fornecedor_cnpj, fornecedor_razao, versao, tipo_modelo,
                criado_em, atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fornecedor_cnpj, fornecedor_razao, status, None, fornecedor_cnpj, fornecedor_razao, versao, tipo_modelo, ts, ts),
        )
        contrato_id = cur.lastrowid

        # log inicial
        cur.execute(
            """
            INSERT INTO status_log (contrato_id, de_status, para_status, alterado_em, alterado_por)
            VALUES (?, ?, ?, ?, ?)
            """,
            (contrato_id, None, status, ts, None),
        )

        conn.commit()
        conn.close()
        return contrato_id
    except Exception:
        conn.rollback()
        conn.close()
        raise

def atualizar_numero_arquivo(contrato_id: int, numero: str, arquivo: str):
    conn = conectar()
    cur = conn.cursor()
    ts = agora_iso()
    cur.execute(
        "UPDATE contratos SET numero = ?, arquivo = ?, atualizado_em = ? WHERE id = ?",
        (numero, arquivo, ts, contrato_id),
    )
    conn.commit()
    conn.close()

def buscar_contrato_por_id(contrato_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, numero, razao_social, status, arquivo,
               fornecedor_cnpj, fornecedor_razao, COALESCE(versao,0),
               COALESCE(tipo_modelo,''), COALESCE(criado_em,''), COALESCE(atualizado_em,''), COALESCE(finalizado_em,'')
        FROM contratos
        WHERE id = ?
        """,
        (contrato_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row

def atualizar_status(contrato_id: int, novo_status: str, alterado_por: str | None):
    conn = conectar()
    cur = conn.cursor()
    ts = agora_iso()

    cur.execute("SELECT status FROM contratos WHERE id = ?", (contrato_id,))
    r = cur.fetchone()
    de_status = r[0] if r else None

    if novo_status == "FINALIZADO":
        cur.execute(
            "UPDATE contratos SET status = ?, atualizado_em = ?, finalizado_em = ? WHERE id = ?",
            (novo_status, ts, ts, contrato_id),
        )
    else:
        cur.execute(
            "UPDATE contratos SET status = ?, atualizado_em = ? WHERE id = ?",
            (novo_status, ts, contrato_id),
        )

    cur.execute(
        """
        INSERT INTO status_log (contrato_id, de_status, para_status, alterado_em, alterado_por)
        VALUES (?, ?, ?, ?, ?)
        """,
        (contrato_id, de_status, novo_status, ts, alterado_por),
    )

    conn.commit()
    conn.close()

def listar_contratos_por_status(status: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id, numero, razao_social, status, arquivo,
            fornecedor_cnpj, fornecedor_razao, COALESCE(versao,0),
            COALESCE(tipo_modelo,''), COALESCE(criado_em,'')
        FROM contratos
        WHERE status = ?
          AND (excluido_em IS NULL OR excluido_em = '')
        ORDER BY id DESC
        """,
        (status,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def contar_por_status():
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT status, COUNT(*)
        FROM contratos
        WHERE (excluido_em IS NULL OR excluido_em = '')
        GROUP BY status
        """
    )
    rows = cur.fetchall()
    conn.close()
    return {s: int(q) for (s, q) in rows}

def listar_fornecedores_resumo():
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            fornecedor_cnpj,
            fornecedor_razao,
            COUNT(*) AS total,
            COALESCE(MAX(COALESCE(versao,0)), 0) AS max_versao
        FROM contratos
        WHERE fornecedor_cnpj IS NOT NULL AND fornecedor_cnpj != ''
          AND (excluido_em IS NULL OR excluido_em = '')
        GROUP BY fornecedor_cnpj, fornecedor_razao
        ORDER BY fornecedor_razao
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def listar_versoes_por_fornecedor(fornecedor_cnpj: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, numero, status, arquivo, COALESCE(versao,0), COALESCE(tipo_modelo,'')
        FROM contratos
        WHERE fornecedor_cnpj = ?
          AND (excluido_em IS NULL OR excluido_em = '')
        ORDER BY COALESCE(versao,0) DESC
        """,
        (fornecedor_cnpj,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def excluir_contrato(contrato_id: int, justificativa: str, excluido_por: str | None) -> int:
    ts = agora_iso()
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE contratos
        SET excluido_em = ?, excluido_por = ?, excluido_justificativa = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (ts, excluido_por, justificativa, ts, contrato_id),
    )
    afetadas = cur.rowcount
    conn.commit()
    conn.close()
    return afetadas

def obter_status_logs(contrato_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT de_status, para_status, alterado_em
        FROM status_log
        WHERE contrato_id = ?
        ORDER BY id ASC
        """,
        (contrato_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def listar_finalizados():
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, COALESCE(criado_em,''), COALESCE(finalizado_em,'')
        FROM contratos
        WHERE status = 'FINALIZADO'
          AND (excluido_em IS NULL OR excluido_em = '')
          AND COALESCE(criado_em,'') != ''
          AND COALESCE(finalizado_em,'') != ''
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows
