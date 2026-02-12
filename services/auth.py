from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from services.banco import conectar

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def criar_usuario(username: str, senha: str, perfil: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
        (username, _hash_senha(senha), perfil),
    )
    conn.commit()
    conn.close()


def autenticar(username: str, senha: str):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT senha, perfil FROM usuarios WHERE username = ?", (username,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    senha_salva, perfil = row

    # 1) Se for hash reconhecido, verifica normal
    try:
        ok = pwd_context.verify(senha, senha_salva)
        conn.close()
        return perfil if ok else None

    except UnknownHashError:
        # 2) Caso antigo: senha estava salva em texto puro ou formato estranho.
        #    Se bater com a senha digitada, migra pra bcrypt e autentica.
        if senha_salva == senha:
            novo_hash = _hash_senha(senha)
            cur.execute(
                "UPDATE usuarios SET senha = ? WHERE username = ?",
                (novo_hash, username),
            )
            conn.commit()
            conn.close()
            return perfil

        conn.close()
        return None


def garantir_admin_padrao():
    """
    Garante que exista admin e que a senha esteja em BCRYPT válido.
    Se houver admin com senha antiga/estranha, força reset para a senha abaixo.
    """
    senha_admin = "TroqueEssaSenhaAgora!2026"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT senha FROM usuarios WHERE username = 'admin'")
    row = cur.fetchone()

    if not row:
        cur.execute(
            "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
            ("admin", _hash_senha(senha_admin), "ADMIN"),
        )
        conn.commit()
        conn.close()
        return

    senha_salva = row[0]

    # identify() retorna string do esquema OU None (não reconhecido)
    esquema = None
    try:
        esquema = pwd_context.identify(senha_salva)
    except Exception:
        esquema = None

    # Se não reconhece o hash (None), ou seja, é legado -> reseta pra bcrypt
    if esquema is None:
        cur.execute(
            "UPDATE usuarios SET senha = ?, perfil = ? WHERE username = ?",
            (_hash_senha(senha_admin), "ADMIN", "admin"),
        )
        conn.commit()

    conn.close()
