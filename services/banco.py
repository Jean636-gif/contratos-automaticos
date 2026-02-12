import sqlite3


# -----------------------------
# Conexão
# -----------------------------
def conectar():
    return sqlite3.connect("banco.db", check_same_thread=False)


# -----------------------------
# Migração leve (add colunas)
# -----------------------------
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


# -----------------------------
# Criação das tabelas
# -----------------------------
def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha TEXT,
        perfil TEXT
    )
    """)

    cursor.execute("""
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

    # Colunas novas (versões por fornecedor)
    _garantir_coluna(conn, "contratos", "fornecedor_cnpj", "TEXT")
    _garantir_coluna(conn, "contratos", "fornecedor_razao", "TEXT")
    _garantir_coluna(conn, "contratos", "versao", "INTEGER")

    conn.close()


# -----------------------------
# Contratos – operações
# -----------------------------
def proxima_versao_fornecedor(conn, fornecedor_cnpj: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(MAX(COALESCE(versao,0)), 0) + 1 FROM contratos WHERE fornecedor_cnpj = ?",
        (fornecedor_cnpj,)
    )
    return int(cur.fetchone()[0])


def inserir_contrato_fornecedor(fornecedor_cnpj: str, fornecedor_razao: str, status: str) -> int:
    """
    Cria um contrato já com a versão correta do fornecedor e status inicial.
    Retorna o ID do contrato.
    """
    conn = conectar()
    conn.execute("BEGIN")
    try:
        versao = proxima_versao_fornecedor(conn, fornecedor_cnpj)

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO contratos (cnpj, razao_social, status, fornecedor_cnpj, fornecedor_razao, versao)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (fornecedor_cnpj, fornecedor_razao, status, fornecedor_cnpj, fornecedor_razao, versao)
        )

        contrato_id = cur.lastrowid
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
    cur.execute(
        "UPDATE contratos SET numero = ?, arquivo = ? WHERE id = ?",
        (numero, arquivo, contrato_id)
    )
    conn.commit()
    conn.close()


def atualizar_status(contrato_id: int, novo_status: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "UPDATE contratos SET status = ? WHERE id = ?",
        (novo_status, contrato_id)
    )
    conn.commit()
    conn.close()


def buscar_contrato_por_id(contrato_id: int):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, numero, razao_social, status, arquivo, fornecedor_cnpj, fornecedor_razao, COALESCE(versao,0)
        FROM contratos
        WHERE id = ?
        """,
        (contrato_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def listar_contratos():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            id,
            numero,
            razao_social,
            status,
            arquivo,
            fornecedor_cnpj,
            fornecedor_razao,
            COALESCE(versao,0) as versao
        FROM contratos
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def listar_contratos_por_status(status: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            id,
            numero,
            razao_social,
            status,
            arquivo,
            fornecedor_cnpj,
            fornecedor_razao,
            COALESCE(versao,0) as versao
        FROM contratos
        WHERE status = ?
        ORDER BY id DESC
    """, (status,))
    rows = cur.fetchall()
    conn.close()
    return rows


def contar_por_status():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT status, COUNT(*)
        FROM contratos
        GROUP BY status
    """)
    rows = cur.fetchall()
    conn.close()
    return {s: int(q) for (s, q) in rows}


def listar_fornecedores_resumo():
    """
    Retorna lista de fornecedores com:
      fornecedor_cnpj, fornecedor_razao, total_contratos, max_versao
    """
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            fornecedor_cnpj,
            fornecedor_razao,
            COUNT(*) as total,
            COALESCE(MAX(COALESCE(versao,0)), 0) as max_versao
        FROM contratos
        WHERE fornecedor_cnpj IS NOT NULL AND fornecedor_cnpj != ''
        GROUP BY fornecedor_cnpj, fornecedor_razao
        ORDER BY fornecedor_razao
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def listar_versoes_por_fornecedor(fornecedor_cnpj: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, numero, status, arquivo, COALESCE(versao,0)
        FROM contratos
        WHERE fornecedor_cnpj = ?
        ORDER BY COALESCE(versao,0) DESC
    """, (fornecedor_cnpj,))
    rows = cur.fetchall()
    conn.close()
    return rows
